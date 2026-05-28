"""
Session analyzer — orchestrator for the post-session debrief.

Reads a session's frames + lap times, runs corner_grader, highlight_finder,
analytics. Calls coach_engine in POST_SESSION mode for the narrative.
Returns the full visualization bundle the bridge serves to the frontend.

Per ADR-014, the bundle shape IS the contract:
    {
      "scorecard":     {...},
      "highlights":    [...],
      "stats":         {...},
      "smoothness":    {...},
      "consistency":   {...},
      "friction":      {...},
      "hustle_map":    [...],
      "trail_brake":   [...],
      "eob":           {...},
      "slip_band":     {...},
      "incidents":     [...],
      "narrative_md":  "...",
      "next_focus":    [...],
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pitwall.features.track.sonoma as sonoma
from pitwall.features.track.track_loader import load_track, TrackMap
from pitwall.features.track.gold_standard import GoldStandard, load_gold_standard
from pitwall.features.session.corner_grader import (
    extract_corner_passes, grade_session, scorecard_to_dict,
    SessionScorecard, CornerPass,
)
from pitwall.features.session.highlight_finder import find_highlights, highlights_to_dict
import pitwall.features.session.analytics as analytics


# ─── Lap segmentation ─────────────────────────────────────────────────────────


def _segment_into_laps(frames, track: TrackMap) -> tuple[list[int], list[float]]:
    """Assign each frame an integer lap, return per-lap times. Local-minima
    based detector — robust to the dataset's anonymised GPS coords because
    it works in cumulative-distance space, not lat/lon."""
    if not frames or track.track_length <= 0:
        return [0] * len(frames), []
    base_d = frames[0].distance
    track_len = track.track_length
    lap_assign = []
    lap_starts = [0]
    lap = 0
    cur_lap_dist = 0.0

    for i, f in enumerate(frames):
        if i > 0:
            dd = f.distance - frames[i - 1].distance
            if dd < 0:
                dd = 0
            cur_lap_dist += dd
            if cur_lap_dist >= track_len * 0.95:
                lap += 1
                cur_lap_dist = 0.0
                lap_starts.append(i)
        lap_assign.append(lap)

    lap_starts.append(len(frames) - 1)
    lap_times: list[float] = []
    for a, b in zip(lap_starts[:-1], lap_starts[1:]):
        if a >= b:
            continue
        dt = frames[b].timestamp - frames[a].timestamp
        if 60 < dt < 300:
            lap_times.append(dt)
    return lap_assign, lap_times


# ─── The analyzer ─────────────────────────────────────────────────────────────


def analyze_session(
    session_id: str,
    frames,
    *,
    track_json_path: str = None,
    gold_path: str = None,
    repo_root: Path = None,
    coach=None,                   # optional CoachEngine instance for narrative
    driver_level: str = "intermediate",
) -> dict:
    """Produce the full /coach/debrief bundle.

    `frames` is a list of TelemetryFrame (from vbo_parser or the bridge's
    in-memory ring buffer). The function reads track + gold from disk
    using sonoma.* paths if not specified.
    """
    if repo_root is None:
        # session → features → pitwall → edge-daemon → apps → repo root.
        repo_root = Path(__file__).resolve().parents[5]
    if track_json_path is None:
        track_json_path = str(repo_root / sonoma.TRACK_JSON_RELATIVE)
    if gold_path is None:
        gold_path = str(repo_root / sonoma.GOLD_STANDARD_RELATIVE)

    track = load_track(track_json_path)
    gold: Optional[GoldStandard] = None
    try:
        gold = load_gold_standard(gold_path)
    except Exception as e:
        # No gold yet — return a minimal bundle that the frontend can still render
        return _no_gold_bundle(session_id, frames, track, str(e))

    lap_assign, lap_times = _segment_into_laps(frames, track)
    passes = extract_corner_passes(frames, track, lap_assign)
    scorecard = grade_session(passes, gold, session_id, lap_times)
    highlights = find_highlights(passes, scorecard.corners, gold, frames, max_items=8)

    # Analytics layer
    gold_entry_speeds = {name: p.entry_speed_kmh for name, p in gold.corners.items()}
    bundle: dict = {
        "session_id":   session_id,
        "track":        sonoma.TRACK_NAME,
        "scorecard":    scorecard_to_dict(scorecard),
        "highlights":   highlights_to_dict(highlights),
        "stats":        analytics.stat_cards(frames),
        "smoothness":   analytics.smoothness_per_corner(passes, frames, track),
        "consistency":  analytics.consistency(passes, lap_times),
        "friction":     analytics.friction_circle(frames),
        "hustle_map":   analytics.hustle_map(frames, segment_m=50,
                                             track_len=track.track_length),
        "track_out":    analytics.track_out_usage(frames, track),
        "trail_brake":  analytics.trail_brake_events(passes),
        "eob":          analytics.eob_summary(passes),
        "slip_band":    analytics.slip_angle_band(frames),
        "slip_oscillations": analytics.slip_oscillation_events(frames),
        "change_of_speed_events": analytics.change_in_speed_events(
            frames, gold_entry_speeds, track,
        ),
        "incidents":    analytics.flight_recorder(frames, track=track),
    }

    # Narrative + next-focus from the LLM coach (or template fallback)
    bundle["narrative_md"], bundle["next_focus"] = _narrate(
        bundle, coach=coach, driver_level=driver_level,
    )
    return bundle


def _no_gold_bundle(session_id: str, frames, track, err: str) -> dict:
    """Bundle returned when no gold standard is available yet."""
    return {
        "session_id":   session_id,
        "track":        sonoma.TRACK_NAME,
        "scorecard":    None,
        "highlights":   [],
        "stats":        analytics.stat_cards(frames),
        "smoothness":   {},
        "consistency":  {},
        "friction":     analytics.friction_circle(frames),
        "hustle_map":   analytics.hustle_map(frames, track_len=track.track_length),
        "track_out":    {},
        "trail_brake":  [],
        "eob":          {},
        "slip_band":    analytics.slip_angle_band(frames),
        "slip_oscillations": analytics.slip_oscillation_events(frames),
        "change_of_speed_events": [],
        "incidents":    analytics.flight_recorder(frames, track=track),
        "narrative_md": (
            f"# Session {session_id}\n\n"
            f"_Gold standard not available_ ({err}). "
            "Run `python3 scripts/extract_gold_lap.py` to freeze a reference, "
            "then re-run the debrief."
        ),
        "next_focus":   [],
    }


def _narrate(bundle: dict, coach=None, driver_level: str = "intermediate") -> tuple[str, list[str]]:
    """Build the narrative + next-focus list. Uses the LLM coach if available
    in POST_SESSION mode; otherwise falls back to a templated debrief."""
    sc = bundle.get("scorecard") or {}
    if not sc:
        return bundle.get("narrative_md", ""), []

    # If coach is provided + supports POST_SESSION, delegate
    if coach is not None and hasattr(coach, "debrief"):
        try:
            result = coach.debrief(bundle, driver_level=driver_level)
            # New (text, focus, emotion) shape; old (text, focus) tolerated.
            if len(result) == 3:
                text, focus, _emotion = result
            else:
                text, focus = result
            if text:
                return text, focus
        except Exception:
            pass

    # Templated fallback — coach voice grounded in T-Rod + Sonoma intel
    sg = sc.get("session_grade", "?")
    best = sc.get("best_lap_s", 0)
    gold_lap = sc.get("gold_lap_s", 0)
    delta = best - gold_lap
    summary = sc.get("summary", "")

    # Worst-graded corner drives the headline focus
    corners = sc.get("corners", [])
    worst = min(corners, key=lambda c: c["score_pct"]) if corners else None
    best_corner = max(corners, key=lambda c: c["score_pct"]) if corners else None

    sections = [f"# Session debrief — {bundle.get('track', 'Sonoma Raceway')}\n"]
    sections.append(
        f"**Best lap:** {best:.2f} s &nbsp;·&nbsp; "
        f"**Gold:** {gold_lap:.2f} s &nbsp;·&nbsp; "
        f"**Δ:** {delta:+.2f} s &nbsp;·&nbsp; "
        f"**Session grade:** **{sg}**\n"
    )
    sections.append(f"_{summary}_\n")

    if worst:
        biggest_loss = (
            max(worst.get("time_loss_attribution", []), key=lambda a: a["seconds_lost"])
            if worst.get("time_loss_attribution") else None
        )
        sections.append(f"### Biggest leverage corner: {worst['corner']}")
        sections.append(
            f"Graded **{worst['grade']}** ({worst['score_pct']:.0%}). "
            f"Δt vs gold: **+{worst['delta_time_s']:.2f} s**. "
            f"Apex {worst['apex_delta_kmh']:+.1f} km/h, "
            f"exit {worst['exit_delta_kmh']:+.1f} km/h, "
            f"brake point {worst['brake_point_delta_m']:+.1f} m."
        )
        if biggest_loss:
            sections.append(
                f"_Time loss source:_ **{biggest_loss['cause']}** — "
                f"{biggest_loss['detail']} ({biggest_loss['seconds_lost']:.2f} s)."
            )
        sections.append(f"_Coach voice:_ {worst['trod_voice']}\n")

    # Highlights
    hs = bundle.get("highlights") or []
    if hs:
        sections.append("### Top moments this session")
        for h in hs[:5]:
            sections.append(f"- **{h['title']}** — {h['narrative_seed']}")
        sections.append("")

    # Stat cards
    stats = bundle.get("stats") or {}
    if stats:
        sections.append("### Session stats")
        sections.append(
            f"- Top speed: **{stats.get('top_speed_kmh', '—')} km/h**\n"
            f"- Max combo G: **{stats.get('max_combo_g', '—')} G**\n"
            f"- Max brake: **{stats.get('max_brake_bar', '—')} bar**\n"
            f"- Longest 100% throttle: **{stats.get('longest_full_throttle_s', '—')} s**\n"
            f"- Laps completed: **{sc.get('n_laps', 0)}**"
        )
        sections.append("")

    # Slip-angle band
    sb = bundle.get("slip_band") or {}
    if sb.get("interpretation"):
        sections.append(f"### Slip-angle band: {sb.get('dominant_band', 'unknown')}")
        sections.append(f"_{sb['interpretation']}_\n")

    # Next focus
    focus: list[str] = []
    if worst:
        focus.append(
            f"{worst['corner']} — focus on the biggest cause: "
            f"{worst.get('time_loss_attribution', [{}])[0].get('cause', 'apex speed')}"
            if worst.get("time_loss_attribution") else
            f"{worst['corner']} — biggest leverage corner this session"
        )
    eob = bundle.get("eob") or {}
    if eob.get("worst_corner"):
        focus.append(
            f"{eob['worst_corner']} — minimise the brake-off → throttle-on gap "
            f"(currently {eob.get('per_corner_avg_s', {}).get(eob['worst_corner'], 0):.2f} s)"
        )
    if best_corner and best_corner["score_pct"] > 0.92:
        focus.append(
            f"Keep doing what you did at {best_corner['corner']} ({best_corner['grade']})"
        )
    focus = focus[:3]
    if focus:
        sections.append("### Next session focus")
        for f in focus:
            sections.append(f"- {f}")

    return "\n\n".join(sections), focus


__all__ = ["analyze_session"]
