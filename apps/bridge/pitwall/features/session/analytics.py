"""
Session analytics for Sonoma — every quantitative metric ADR-014 enumerates
that isn't covered by corner_grader (per-corner A-F + time-loss).

Categories:
- Smoothness   : steering / brake / throttle derivative variance per corner
- Friction     : circle utilisation histogram (gLat × gLong fill)
- Hustle       : per-segment 100 % throttle fraction
- Track-out    : cross-track error to reference line
- Consistency  : lap-time + per-corner-time std dev
- EoB summary  : per-session aggregate of brake-off → throttle-on gaps
- Trail brake  : detected events + release-rate score
- Bentley bands: slip-angle 4-band classifier (PDF p15)
- Limit osc    : Bentley archetypes #1 / #2 / #3 (PDF p42)
- Plateau      : stepped-learning detector across sessions (PDF p26)
- Change-speed : Bentley p38 — "throttle to find the limit" misread
- Stat cards   : top speed, max G, max brake bar, longest 100% throttle stretch

Every function takes plain inputs and returns plain dicts so the bridge
can serialise them straight to JSON.
"""
from __future__ import annotations

import math
import statistics
from typing import Optional

import pitwall.features.track.sonoma as sonoma
from pitwall.features.session.corner_grader import CornerPass


# ─── Stat cards ───────────────────────────────────────────────────────────────


def stat_cards(frames) -> dict:
    """Compute session-level statistics for the dashboard stat cards."""
    if not frames:
        return {}
    speeds_kmh = [f.speed * 3.6 for f in frames]
    combos = [f.combo_g for f in frames]
    brakes = [f.brake_pressure for f in frames]

    longest_full_throttle_s = 0.0
    cur_run = 0.0
    for j, f in enumerate(frames[:-1]):
        if f.throttle >= 95:
            dt = frames[j + 1].timestamp - f.timestamp
            cur_run += dt
            longest_full_throttle_s = max(longest_full_throttle_s, cur_run)
        else:
            cur_run = 0.0

    return {
        "top_speed_kmh":              round(max(speeds_kmh), 1),
        "max_combo_g":                round(max(combos), 2),
        "max_brake_bar":              round(max(brakes), 1),
        "longest_full_throttle_s":    round(longest_full_throttle_s, 2),
        "average_speed_kmh":          round(statistics.mean(speeds_kmh), 1),
        "n_frames":                   len(frames),
        "session_duration_s":         round(frames[-1].timestamp - frames[0].timestamp, 1),
    }


# ─── Smoothness ───────────────────────────────────────────────────────────────


def smoothness_per_corner(passes: list[CornerPass], frames, track) -> dict:
    """Std-dev of d/dt of (steering, brake, throttle) per corner pass.
    Lower = smoother per Bentley's "smooth is fast" axiom.

    Takes a TrackMap so corner entry/exit distances are real, not stubbed.
    Returns the BEST (lowest steering-dot std) pass per corner — same
    convention as the scorecard.
    """
    track_len = track.track_length if hasattr(track, "track_length") else 4258
    corner_bounds = {
        c.name: (c.entry_distance, c.exit_distance)
        for c in getattr(track, "corners", [])
    }
    by_corner: dict[str, list[dict]] = {}

    for p in passes:
        bounds = corner_bounds.get(p.corner)
        if bounds is None:
            continue
        e_d, x_d = bounds
        in_frames = []
        for f in frames:
            d = f.distance % track_len if track_len else f.distance
            if e_d <= d <= x_d:
                in_frames.append(f)
        if len(in_frames) < 3:
            continue
        steer_dot = _series_dot([f.steering for f in in_frames],
                                [f.timestamp for f in in_frames])
        brake_dot = _series_dot([f.brake_pressure for f in in_frames],
                                [f.timestamp for f in in_frames])
        thr_dot = _series_dot([f.throttle for f in in_frames],
                              [f.timestamp for f in in_frames])
        by_corner.setdefault(p.corner, []).append({
            "lap":              p.lap,
            "steering_dot_std": round(statistics.stdev(steer_dot) if len(steer_dot) > 1 else 0, 2),
            "brake_dot_std":    round(statistics.stdev(brake_dot) if len(brake_dot) > 1 else 0, 2),
            "throttle_dot_std": round(statistics.stdev(thr_dot)   if len(thr_dot) > 1 else 0, 2),
        })

    best: dict[str, dict] = {}
    for corner, vals in by_corner.items():
        vals.sort(key=lambda v: v["steering_dot_std"])
        best[corner] = vals[0]
    return best


def _series_dot(xs, ts):
    out = []
    for j in range(1, len(xs)):
        dt = ts[j] - ts[j - 1]
        if dt > 0:
            out.append((xs[j] - xs[j - 1]) / dt)
    return out


# ─── Friction circle ──────────────────────────────────────────────────────────


def friction_circle(frames, max_combo_g_observed: float = 2.29,
                     n_samples: int = 1500) -> dict:
    """Histogram + utilisation summary across the session.
    Used by /session/<id>/friction_circle and the post-session debrief.

    `samples` is uniformly stride-sampled so all parts of the session are
    represented in the scatter plot, not just the head of the lap.
    """
    if not frames:
        return {}
    bins = [0] * 10        # 0-10%, 10-20%, ... 90-100%+
    over_limit = 0
    for f in frames:
        util = f.combo_g / max_combo_g_observed if max_combo_g_observed > 0 else 0
        idx = min(int(util * 10), 9)
        bins[idx] += 1
        if util > 1.0:
            over_limit += 1

    # Stride-sample so the whole lap is represented
    stride = max(1, len(frames) // n_samples)
    samples = [
        {"gLat": round(f.g_lat, 3), "gLong": round(f.g_long, 3)}
        for f in frames[::stride]
    ][:n_samples]

    total = max(sum(bins), 1)
    return {
        "max_combo_g_observed": round(max_combo_g_observed, 2),
        "histogram_pct": [round(100 * b / total, 1) for b in bins],
        "over_limit_pct": round(100 * over_limit / total, 2),
        "samples": samples,
    }


# ─── Hustle map ───────────────────────────────────────────────────────────────


def hustle_map(frames, segment_m: float = 50.0, track_len: float = 4258) -> list[dict]:
    """Per-segment fraction of frames at >= 95% throttle. Track painted by
    where the driver actually committed."""
    n_seg = int(track_len / segment_m) + 1
    bins = [{"count": 0, "hustle": 0} for _ in range(n_seg)]
    for f in frames:
        d = f.distance % track_len if track_len else f.distance
        idx = min(int(d / segment_m), n_seg - 1)
        bins[idx]["count"] += 1
        if f.throttle >= 95:
            bins[idx]["hustle"] += 1
    return [
        {"start_m": round(i * segment_m, 1),
         "end_m":   round((i + 1) * segment_m, 1),
         "hustle_pct": round(100 * b["hustle"] / b["count"], 1) if b["count"] else 0}
        for i, b in enumerate(bins)
    ]


# ─── Track-out usage ──────────────────────────────────────────────────────────


def track_out_usage(frames, track) -> dict:
    """Mean cross-track-error to the reference line — proxy for "use all the track".
    Bentley: 1 ft from the edge already shrinks the radius noticeably."""
    from pitwall.features.track.track_loader import cross_track_error
    deviations = []
    for f in frames:
        try:
            xte = cross_track_error(track, f.distance, f.lat, f.lon)
            deviations.append(xte)
        except Exception:
            continue
    if not deviations:
        return {}
    return {
        "mean_xte_m":     round(statistics.mean(deviations), 2),
        "p95_xte_m":      round(sorted(deviations)[int(len(deviations) * 0.95)], 2),
        "max_xte_m":      round(max(deviations), 2),
        "samples":        len(deviations),
    }


# ─── Consistency ──────────────────────────────────────────────────────────────


def consistency(passes: list[CornerPass], lap_times_s: list[float]) -> dict:
    """Lap-time + per-corner-time std dev. Identifies the "one corner that
    varies most" → feeds pre-brief input."""
    by_corner: dict[str, list[float]] = {}
    for p in passes:
        by_corner.setdefault(p.corner, []).append(p.corner_time_s)
    most_variable: Optional[tuple[str, float]] = None
    for corner, times in by_corner.items():
        if len(times) < 2:
            continue
        sd = statistics.stdev(times)
        if not most_variable or sd > most_variable[1]:
            most_variable = (corner, sd)
    return {
        "lap_time_std":      round(statistics.stdev(lap_times_s), 3) if len(lap_times_s) > 1 else 0,
        "lap_time_spread":   round(max(lap_times_s) - min(lap_times_s), 3) if lap_times_s else 0,
        "most_variable_corner": (
            {"corner": most_variable[0], "std_s": round(most_variable[1], 3)}
            if most_variable else None
        ),
        "per_corner_std": {
            corner: round(statistics.stdev(times), 3) if len(times) > 1 else 0
            for corner, times in by_corner.items()
        },
    }


# ─── EoB / "nothing time" summary ─────────────────────────────────────────────


def eob_summary(passes: list[CornerPass]) -> dict:
    """Per-corner average nothing_time. Bentley: best drivers minimise this."""
    by_corner: dict[str, list[float]] = {}
    for p in passes:
        if p.nothing_time_s > 0:
            by_corner.setdefault(p.corner, []).append(p.nothing_time_s)
    return {
        "average_nothing_time_s": (
            round(statistics.mean(
                [t for ts in by_corner.values() for t in ts]
            ), 3) if by_corner else 0.0
        ),
        "worst_corner": (
            max(((corner, statistics.mean(ts))
                 for corner, ts in by_corner.items()),
                key=lambda x: x[1])[0] if by_corner else None
        ),
        "per_corner_avg_s": {
            corner: round(statistics.mean(ts), 3)
            for corner, ts in by_corner.items()
        },
    }


# ─── Bentley slip-angle band classifier ───────────────────────────────────────


def slip_angle_band(frames, max_combo_g_observed: float = 2.29) -> dict:
    """Bentley PDF p15 — 4 bands by friction utilisation.
    Returns the dominant band + percentage spent in each."""
    if not frames:
        return {}
    band_frames = {"under_driving": 0, "approaching_peak": 0,
                   "at_peak": 0, "over_driving": 0}
    for f in frames:
        util = f.combo_g / max_combo_g_observed if max_combo_g_observed > 0 else 0
        if util < 0.55:
            band_frames["under_driving"] += 1
        elif util < 0.80:
            band_frames["approaching_peak"] += 1
        elif util < 0.95:
            band_frames["at_peak"] += 1
        else:
            band_frames["over_driving"] += 1

    total = sum(band_frames.values())
    pct = {k: round(100 * v / total, 1) for k, v in band_frames.items()}
    dominant = max(pct.items(), key=lambda kv: kv[1])[0]
    interpretation = {
        "under_driving":      "Living below the limit — leave grip on the table. Bentley's far-left band.",
        "approaching_peak":   "Middle-left band — could be faster with more commitment, low tire wear.",
        "at_peak":            "Peak traction zone — the goal band. Sustainable lap pace.",
        "over_driving":       "Beyond the peak — sliding through corners. Far-right band, high tire wear.",
    }[dominant]
    return {
        "dominant_band": dominant,
        "interpretation": interpretation,
        "pct_per_band": pct,
    }


# ─── ADR-018: slip-angle oscillation detector ────────────────────────────────


def slip_oscillation_events(frames, *, window_s: float = 3.0,
                            min_band_crossings: int = 4,
                            stride_s: float = 0.5) -> list[dict]:
    """Detect intermediate-driver "ego oscillation" — rapid swings between
    `at_peak` / `over_driving` and back down. Signals a driver chasing the
    limit by overshoot rather than building up to it; the canonical cue is
    'smooth is fast, dial it back to 90 percent.'

    Returns a list of ``{t_start, t_end, crossings, peak_combo_g, severity}``
    events where a sliding `window_s` second window saw at least
    `min_band_crossings` changes between adjacent friction bands.

    The detector is intentionally coarse — at HPDE level we don't need to
    distinguish under-→approach noise; we want the case where the driver
    keeps blowing past peak grip and reining it back in, repeatedly.
    """
    if not frames or len(frames) < 4:
        return []

    # Reuse the band classifier's thresholds for consistency.
    max_g = max((f.combo_g for f in frames), default=2.29) or 2.29

    def _band(f) -> int:
        util = f.combo_g / max_g
        if util < 0.55: return 0
        if util < 0.80: return 1
        if util < 0.95: return 2
        return 3

    # Collect (t, band) pairs.
    series = [(f.timestamp, _band(f)) for f in frames]
    events: list[dict] = []
    n = len(series)
    i = 0
    last_event_end = -1.0
    while i < n:
        t0 = series[i][0]
        # Find window end
        j = i
        while j < n and series[j][0] - t0 <= window_s:
            j += 1
        # Count band crossings inside [i, j)
        crossings = 0
        peak_g = 0.0
        for k in range(i + 1, j):
            if series[k][1] != series[k - 1][1]:
                crossings += 1
            if frames[k].combo_g > peak_g:
                peak_g = frames[k].combo_g
        if crossings >= min_band_crossings and t0 > last_event_end:
            events.append({
                "t_start":       round(float(t0), 3),
                "t_end":         round(float(series[min(j, n) - 1][0]), 3),
                "crossings":     int(crossings),
                "peak_combo_g":  round(float(peak_g), 3),
                "severity":      "high" if crossings >= min_band_crossings + 2 else "medium",
            })
            last_event_end = series[min(j, n) - 1][0]
        # Slide window forward by ~stride_s
        target = t0 + stride_s
        while i < n and series[i][0] < target:
            i += 1
        if i == 0:
            i = 1
    return events


# ─── Bentley change-in-speed problem detector ─────────────────────────────────


def change_in_speed_events(frames, gold_entry_speeds: dict[str, float],
                            track) -> list[dict]:
    """Bentley PDF p38 — driver enters under-limit and adds throttle to find
    the limit, getting power-on understeer/oversteer. Detect:
        throttle_dot > 0 AND |gLat| > 0.5G AND speed < gold_entry_speed."""
    events = []
    for j in range(1, len(frames)):
        f = frames[j]
        prev = frames[j - 1]
        dt = f.timestamp - prev.timestamp
        if dt <= 0:
            continue
        thr_dot = (f.throttle - prev.throttle) / dt
        if thr_dot < 5:
            continue
        if abs(f.g_lat) < 0.5:
            continue
        d = f.distance % track.track_length if track.track_length else f.distance
        # Find which corner we're in
        for c in track.corners:
            if c.entry_distance <= d <= c.exit_distance:
                gold_v = gold_entry_speeds.get(c.name)
                if gold_v and f.speed * 3.6 < gold_v - 1.0:
                    events.append({
                        "timestamp":    round(f.timestamp, 2),
                        "distance_m":   round(d, 1),
                        "corner":       c.name,
                        "speed_kmh":    round(f.speed * 3.6, 1),
                        "gold_kmh":     round(gold_v, 1),
                        "g_lat":        round(f.g_lat, 2),
                        "throttle_dot": round(thr_dot, 1),
                    })
                break
    # De-duplicate consecutive events (within 0.5s of each other)
    deduped = []
    for e in events:
        if not deduped or e["timestamp"] - deduped[-1]["timestamp"] > 0.5:
            deduped.append(e)
    return deduped


# ─── Trail-brake events + release-rate score ──────────────────────────────────


def trail_brake_events(passes: list[CornerPass]) -> list[dict]:
    """Detect explicit trail-brake events. A pass qualifies when:
        peak_brake_bar > 10 AND trail_brake_bar_at_apex > 1
    Score the release-rate quality on 0..1."""
    out = []
    for p in passes:
        if p.peak_brake_bar < 10 or p.trail_brake_bar_at_apex < 1:
            continue
        # Quality: ideal trail releases smoothly to ~5-15% peak at apex.
        target = max(p.peak_brake_bar * 0.10, 3.0)
        gap = abs(p.trail_brake_bar_at_apex - target)
        quality = max(0.0, 1.0 - gap / max(p.peak_brake_bar * 0.20, 5.0))
        out.append({
            "lap":     p.lap,
            "corner":  p.corner,
            "peak_bar": round(p.peak_brake_bar, 1),
            "apex_bar": round(p.trail_brake_bar_at_apex, 1),
            "quality": round(quality, 3),
        })
    return out


# ─── Black-box flight recorder ────────────────────────────────────────────────


def flight_recorder(frames, max_combo_g_threshold: float = 2.0,
                    xte_threshold_m: float = 5.0, track=None) -> list[dict]:
    """Auto-save 30 s windows around over-limit / off-track events."""
    incidents = []
    for j, f in enumerate(frames):
        triggered = False
        reason = ""
        if f.combo_g > max_combo_g_threshold:
            triggered = True
            reason = f"combo G {f.combo_g:.2f} > {max_combo_g_threshold}"
        if track:
            try:
                from pitwall.features.track.track_loader import cross_track_error
                xte = cross_track_error(track, f.distance, f.lat, f.lon)
                if xte > xte_threshold_m:
                    triggered = True
                    reason = f"off-line {xte:.1f} m"
            except Exception:
                pass
        if triggered and (not incidents or f.timestamp - incidents[-1]["timestamp"] > 5):
            incidents.append({
                "timestamp":    round(f.timestamp, 2),
                "distance_m":   round(f.distance, 1),
                "speed_kmh":    round(f.speed * 3.6, 1),
                "combo_g":      round(f.combo_g, 2),
                "reason":       reason,
                "frame_idx":    j,
            })
    return incidents


# ─── Limit oscillation classifier (longitudinal) ──────────────────────────────


def limit_oscillation(corner_grade_history: list[dict]) -> dict:
    """Bentley PDF p42 — driver archetypes #1 (never reaches limit), #2
    (oscillates), #3 (settles slightly above). Computed from cross-session
    corner-grade variance. Input: list of {session_id, corner, score_pct}."""
    if not corner_grade_history:
        return {"archetype": "unknown", "reason": "no longitudinal data"}
    by_corner: dict[str, list[float]] = {}
    for h in corner_grade_history:
        by_corner.setdefault(h["corner"], []).append(h["score_pct"])
    avg_score = statistics.mean(h["score_pct"] for h in corner_grade_history)
    avg_var = statistics.mean(
        statistics.stdev(scores) if len(scores) > 1 else 0
        for scores in by_corner.values()
    )
    if avg_score < 0.75:
        return {"archetype": "1_under_limit", "reason": "rarely reaches the peak band"}
    if avg_var > 0.10:
        return {"archetype": "2_oscillating", "reason": "high session-to-session variance"}
    return {"archetype": "3_at_limit", "reason": "consistently in the peak band"}


# ─── Plateau detector (longitudinal) ──────────────────────────────────────────


def plateau_detector(session_lap_times: list[tuple[str, float]],
                     window: int = 3,
                     tol_s: float = 0.10) -> dict:
    """Bentley PDF p26 — detect a plateau in best-lap-time across sessions.
    Input: [(session_id, best_lap_s), ...] in chronological order.

    A plateau means the *most recent* `window` sessions are all within
    `tol_s` of the best time achieved across them — i.e. no meaningful
    improvement has happened in that window. An improving streak should
    NOT be classified as a plateau.
    """
    if len(session_lap_times) < window:
        return {"plateau": False, "reason": "not enough sessions",
                "streak_length": len(session_lap_times)}

    best_overall = min(t for _, t in session_lap_times)

    # Walk from newest backward; count how many recent sessions are
    # within `tol_s` of the best across them. Break on a session that's
    # significantly slower (which would indicate improvement happened after).
    recent = list(reversed(session_lap_times))
    best_recent = recent[0][1]
    streak = 0
    plateau_start = None
    for sid, t in recent:
        best_recent = min(best_recent, t)
        if t <= best_recent + tol_s:
            streak += 1
            plateau_start = sid
        else:
            break

    is_plateau = streak >= window and abs(best_recent - best_overall) < tol_s
    return {
        "plateau":        is_plateau,
        "streak_length":  streak,
        "best_lap_s":     round(best_recent, 3),
        "started_after":  plateau_start,
        "reason":         (f"no improvement in last {streak} sessions"
                           if is_plateau else "still improving"),
    }


__all__ = [
    "stat_cards", "smoothness_per_corner", "friction_circle", "hustle_map",
    "track_out_usage", "consistency", "eob_summary", "slip_angle_band",
    "change_in_speed_events", "trail_brake_events", "flight_recorder",
    "limit_oscillation", "plateau_detector",
]
