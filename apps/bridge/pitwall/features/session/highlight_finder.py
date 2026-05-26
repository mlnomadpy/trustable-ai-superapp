"""
Highlight-moment finder for Sonoma sessions.

Per ADR-014 catalog, ranks the top-N "interesting" moments per session
across Sonoma-specific categories. Output feeds:
  - the post-session LLM prompt (so the narrative can name specific moments)
  - the /session/<id>/highlights endpoint (so the frontend can render
    a highlights reel with auto-clipped video cut points)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

import pitwall.features.track.sonoma as sonoma
from pitwall.features.session.corner_grader import CornerPass, CornerGrade
from pitwall.features.track.gold_standard import GoldStandard


@dataclass
class Highlight:
    """A notable session moment for the highlights reel and LLM prompt."""
    title: str
    category: str
    severity: str            # "high" | "medium" | "positive" | "engineering"
    lap: int
    distance_m: float
    timestamp_s: float       # in-session second
    video_in_s: float        # = timestamp_s - 3
    video_out_s: float       # = timestamp_s + 5
    narrative_seed: str      # short, fed to the LLM for richer phrasing


def find_highlights(passes: list[CornerPass], grades: list[CornerGrade],
                    gold: GoldStandard, frames,
                    max_items: int = 8) -> list[Highlight]:
    """Rank the top-N interesting moments across Sonoma-specific categories."""
    out: list[Highlight] = []

    # Build a quick index of grade by (corner, lap)
    grade_by_key = {(g.corner, 0): g for g in grades}    # scorecard collapses laps

    for p in passes:
        gold_pass = gold.corners.get(p.corner)
        if not gold_pass:
            continue

        # Approximate timestamp at corner apex
        apex_ts = _approx_apex_timestamp(frames, p, gold_pass)

        # 1. T6 Carousel oversteer — combo G > 1.6 in the corner window
        if p.corner == "Turn 6" and p.max_combo_g > 1.6:
            out.append(Highlight(
                title=f"T6 Carousel — {p.max_combo_g:.2f}G peak (lap {p.lap})",
                category="t6_carousel_oversteer",
                severity="high",
                lap=p.lap,
                distance_m=gold_pass.apex_distance_m,
                timestamp_s=apex_ts,
                video_in_s=max(0, apex_ts - 3),
                video_out_s=apex_ts + 5,
                narrative_seed=(
                    f"Lap {p.lap}, the Carousel — combo G hit {p.max_combo_g:.2f}, "
                    f"likely off-camber sliding. T-Rod: 'smooth exit, no early throttle'."
                ),
            ))

        # 2. T11 bump late brake — brake_point closer to entry than gold by >5m
        if p.corner == "Turn 11" and (gold_pass.brake_point_m - p.brake_point_m) > 5:
            out.append(Highlight(
                title=f"T11 brake — {gold_pass.brake_point_m - p.brake_point_m:.0f} m past the bump (lap {p.lap})",
                category="t11_bump_late_brake",
                severity="high",
                lap=p.lap,
                distance_m=gold_pass.apex_distance_m,
                timestamp_s=apex_ts,
                video_in_s=max(0, apex_ts - 4),
                video_out_s=apex_ts + 6,
                narrative_seed=(
                    f"Calamity Corner, lap {p.lap} — you started braking "
                    f"{gold_pass.brake_point_m - p.brake_point_m:.0f} m later than gold. "
                    f"Wait for the bump to settle next time."
                ),
            ))

        # 3. T10 lift-when-brake-needed — opposite of usual: braking when gold lifts
        if p.corner == "Turn 10" and p.peak_brake_bar > 30 and gold_pass.peak_brake_bar < 20:
            out.append(Highlight(
                title=f"T10 over-braked — {p.peak_brake_bar:.0f} bar (gold {gold_pass.peak_brake_bar:.0f})",
                category="t10_lift_when_brake_needed",
                severity="medium",
                lap=p.lap,
                distance_m=gold_pass.apex_distance_m,
                timestamp_s=apex_ts,
                video_in_s=max(0, apex_ts - 3),
                video_out_s=apex_ts + 5,
                narrative_seed=(
                    f"T10 lap {p.lap} — you used {p.peak_brake_bar:.0f} bar; gold uses "
                    f"only {gold_pass.peak_brake_bar:.0f}. T-Rod: 'lift, don't brake'."
                ),
            ))

        # 4. Coasting in corner — Bentley's #1 wasted-time signal
        if p.coast_seconds > 0.4:
            out.append(Highlight(
                title=f"{p.corner} — {p.coast_seconds:.1f}s coasting (lap {p.lap})",
                category="coast_in_corner",
                severity="medium",
                lap=p.lap,
                distance_m=gold_pass.apex_distance_m,
                timestamp_s=apex_ts,
                video_in_s=max(0, apex_ts - 3),
                video_out_s=apex_ts + 4,
                narrative_seed=(
                    f"{p.corner}, lap {p.lap} — {p.coast_seconds:.1f}s with no "
                    f"throttle and no brake. T-Rod: 'just go 100'."
                ),
            ))

        # 5. Perfect trail brake at T4 — positive highlight.
        # A clean trail releases to ~5-20 % of peak by apex.
        if p.corner == "Turn 4" and p.peak_brake_bar > 15 and 0.05 <= (
            p.trail_brake_bar_at_apex / max(p.peak_brake_bar, 1)
        ) <= 0.20:
            out.append(Highlight(
                title=f"T4 — clean trail brake (lap {p.lap})",
                category="perfect_trail_brake_T4",
                severity="positive",
                lap=p.lap,
                distance_m=gold_pass.apex_distance_m,
                timestamp_s=apex_ts,
                video_in_s=max(0, apex_ts - 3),
                video_out_s=apex_ts + 4,
                narrative_seed=(
                    f"T4 lap {p.lap} — brake taper was clean, "
                    f"{p.trail_brake_bar_at_apex:.0f} bar at apex. Keep doing this."
                ),
            ))

        # 6. T9 pinching into T10 — exit speed at T9 < gold by >3 km/h
        if p.corner == "Turn 9" and (gold_pass.exit_speed_kmh - p.exit_speed_kmh) > 3:
            out.append(Highlight(
                title=f"T9 exit — {gold_pass.exit_speed_kmh - p.exit_speed_kmh:.0f} km/h slow vs gold (lap {p.lap})",
                category="t9_pinch_into_t10",
                severity="medium",
                lap=p.lap,
                distance_m=gold_pass.exit_distance_m,
                timestamp_s=apex_ts + 1.0,
                video_in_s=max(0, apex_ts - 1),
                video_out_s=apex_ts + 5,
                narrative_seed=(
                    f"T9 lap {p.lap} — exit {p.exit_speed_kmh:.0f} km/h vs gold "
                    f"{gold_pass.exit_speed_kmh:.0f}. T-Rod: 'open up nine, straight shot to ten'."
                ),
            ))

    # 7. Improvement vs prior pass at same corner
    by_corner: dict[str, list[CornerPass]] = {}
    for p in passes:
        by_corner.setdefault(p.corner, []).append(p)
    for corner, ps in by_corner.items():
        if len(ps) < 2:
            continue
        ps.sort(key=lambda p: p.lap)
        first = ps[0]
        best = max(ps, key=lambda p: p.exit_speed_kmh)
        if best.exit_speed_kmh - first.exit_speed_kmh > 2 and best.lap > first.lap:
            apex_ts = _approx_apex_timestamp(frames, best, gold.corners.get(corner))
            out.append(Highlight(
                title=f"{corner} — exit speed +{best.exit_speed_kmh - first.exit_speed_kmh:.1f} km/h",
                category="improved_corner_vs_first",
                severity="positive",
                lap=best.lap,
                distance_m=(gold.corners[corner].exit_distance_m
                            if corner in gold.corners else 0),
                timestamp_s=apex_ts,
                video_in_s=max(0, apex_ts - 3),
                video_out_s=apex_ts + 4,
                narrative_seed=(
                    f"{corner} — exit speed climbed from {first.exit_speed_kmh:.1f} to "
                    f"{best.exit_speed_kmh:.1f} km/h between lap {first.lap} and lap {best.lap}."
                ),
            ))

    # Severity ordering: high > medium > positive > engineering
    severity_rank = {"high": 0, "medium": 1, "positive": 2, "engineering": 3}
    out.sort(key=lambda h: (severity_rank.get(h.severity, 9), -h.timestamp_s))
    return out[:max_items]


def _approx_apex_timestamp(frames, p: CornerPass, gold_pass) -> float:
    """Find the frame closest to the corner's apex distance and return its
    in-session timestamp (relative to first frame)."""
    if not frames or not gold_pass:
        return 0.0
    base_ts = frames[0].timestamp
    apex_d = gold_pass.apex_distance_m
    best = min(frames, key=lambda f: abs((f.distance % 4258) - apex_d))
    return round(best.timestamp - base_ts, 2)


def highlights_to_dict(hs: list[Highlight]) -> list[dict]:
    """Serialise a list of Highlights to JSON-safe dicts."""
    return [asdict(h) for h in hs]


__all__ = ["Highlight", "find_highlights", "highlights_to_dict"]
