# Track Markers

A **marker** is a named visual or physical reference point that drivers actually use on track — "the bridge", "the bump where the road widens", "the Toyota sign letters", "the K-wall bend". Pace-note coaching that names these markers sounds native; coaching that says "brake at 124 metres" does not.

Markers are loaded from the track JSON, exposed via `track_loader.MarkerDef`, and surfaced into pace-note phrasing by `coach_engine.RuleCoach` and any LLM coach that consumes `CoachContext.next_brake_marker_label`.

---

## Why markers (Sonoma intel finding)

The [Sonoma track intelligence doc](sonoma_track_intelligence.md) found, after surveying every public track guide, that **Sonoma's reference vocabulary is environmental, not numeric**. Pros call out bridges, tire stacks, sign letters, pavement cracks, K-wall bends, pit-entry lines, and "the bump" — not "the 100 board" or distances in metres. Coaching language must follow.

Concrete impact on our coach output:

| Before markers | After markers |
|---|---|
| `185, left 6, brake 50, uphill` | `185, left 6, brake at the bridge, uphill` |
| `230, right 3, brake 134, late apex` | `230, Calamity Corner, brake at the bump where the road widens left, late apex` |
| `128, right 3, brake 86, downhill` | `128, the Carousel, brake at just after the slight crest, downhill` |
| `91, right 6, brake 0, late apex` | `91, right 6, brake at the 300 board, late apex` |

Verified on a full Sonoma replay: **42 % of the 186 pace notes per lap now reference a real Sonoma landmark**.

---

## Schema

The markers schema is co-located with the corner data in the track JSON. Each marker is also flattened into a top-level `markers: []` array so consumers can do a single nearest-marker search without iterating corners.

```json
{
  "id": "T11_bump",
  "kind": "brake_ref",
  "label": "the bump where the road widens left",
  "distance": 4080.0,
  "corner": "Turn 11",
  "source": "blayze",
  "note": "best brake reference — wait for the car to compress and settle"
}
```

| Field | Meaning |
|---|---|
| `id` | Stable string ID, used for image filenames + cross-references |
| `kind` | One of `brake_ref`, `apex_ref`, `turn_in_ref`, `exit_ref`, `visual`, `nickname` |
| `label` | Human-readable phrase the coach speaks ("the bridge") |
| `distance` | Cumulative track distance in metres (modulo `track_length_m`) |
| `corner` | Canonical corner name this marker belongs to |
| `source` | Attribution: `kanga`, `blayze`, `lapmeta`, `bentley`, etc. |
| `note` | Optional caveat or selection hint |

In the per-corner block, each marker also carries `at_offset_m_from_entry` (positive = before entry, zero = at entry, negative = after entry) so future tooling can re-derive `distance` if the geometry changes.

Per-corner enrichment also adds:

```json
{
  "name": "Turn 11",
  "nicknames": ["Calamity Corner", "the hairpin"],
  "coaching_tip": "wait for the bump to settle, trail to the apex, all the road on exit",
  "markers": [...]
}
```

---

## Sonoma marker inventory

16 markers across 8 corners, authored from `docs/sonoma_track_intelligence.md`:

| Corner | Marker ID | Kind | Label | Source |
|---|---|---|---|---|
| Turn 1  | `T1_kwall_bend`            | apex_ref     | the K-wall bend | kanga |
| Turn 2  | `T2_bridge`                | brake_ref    | the bridge | kanga |
| Turn 2  | `T2_pavement_cracks`       | brake_ref    | the pavement cracks | kanga |
| Turn 3  | `T3_right_curbing`         | apex_ref     | the right-hand curbing | kanga |
| Turn 3  | `T3_light_poles`           | visual       | the light poles in the stands | kanga |
| Turn 4  | `T4_left_wall_step`        | brake_ref    | where the left wall steps up | kanga |
| Turn 6  | `T6_crest`                 | brake_ref    | just after the slight crest | kanga |
| Turn 6  | `T6_tires_left`            | brake_ref    | the tire stacks on the left | kanga |
| Turn 6  | `T6_corner_station`        | visual       | the corner station on the right | kanga |
| Turn 7  | `T7_300_board`             | brake_ref    | the 300 board | blayze |
| Turn 10 | `T10_toyota_sign`          | visual       | the Toyota sign letters | kanga |
| Turn 10 | `T10_left_berm`            | apex_ref     | the left berm | kanga |
| Turn 11 | `T11_bump`                 | brake_ref    | the bump where the road widens left | blayze |
| Turn 11 | `T11_pit_entry`            | brake_ref    | the pit-entry lines on the left | kanga |
| Turn 11 | `T11_tire_stack_3`         | apex_ref     | the third tire stack | blayze |
| Turn 11 | `T11_tire_stacks_turnin`   | turn_in_ref  | the start of the tire stacks on the left | blayze |

Corners without authored markers (T5, T8, T9) intentionally fall back to numeric pace notes — the intel doc didn't surface canonical visual references for those.

---

## Per-corner coaching tips

Authored alongside markers, each corner that's covered in the intel doc has a single-sentence coaching cue grounded in either Bentley's actual Sonoma session or per-corner pro guides:

| Corner | Coaching tip |
|---|---|
| Turn 1 | carry throttle through, swing tight to the K-wall bend |
| Turn 2 | you can brake less than you think; carry speed uphill |
| Turn 3 | give-away corner — sacrifice T3 entry to win T3a and T4 |
| Turn 4 | downhill, off-camber — back the brake up by one marker |
| Turn 5 | throwaway corner — preserve T6 entry, breathe the throttle |
| Turn 6 | smooth exit — speed here carries the long straight; no early throttle |
| Turn 7 | eyes up — late turn-in, late apex; second apex matters more |
| Turn 8 | smooth, don't pinch — apexes all slightly late, throttle on exit |
| Turn 9 | setup for T10 — exit T8a at full throttle |
| Turn 10 | lift, don't brake — fastest corner; carry full throttle past apex |
| Turn 11 | wait for the bump to settle, trail to the apex, all the road on exit |

These currently surface in `CoachContext.next_corner_tip` and are available to `LitertCoach` (LiteRT-LM via MediaPipe Genai) for prompt injection. The `RuleCoach` does not voice them directly — they're meant for richer LLM-driven coaching.

---

## Authoring + sync

The canonical track JSON lives at `data/tracks/sonoma.json`. Three duplicates exist (in `src/pitwall/features/`, `flutter/assets/tracks/`, `flutter/android/app/src/main/assets/tracks/`) for different runtime consumers; running `python3 tools/enrich_sonoma_track.py` syncs all four from the canonical source.

To re-author or extend marker data, edit `tools/enrich_sonoma_track.py:ENRICHMENT` (one entry per corner) and re-run:

```
python3 tools/enrich_sonoma_track.py            # enrich + sync all 4 copies
python3 tools/enrich_sonoma_track.py --dry-run  # show summary only
python3 tools/enrich_sonoma_track.py --no-sync  # only edit the canonical copy
```

A `.bak` is written next to the canonical file before any mutation.

---

## Runtime use

In `track_loader.py`:

```python
from track_loader import load_track, find_nearest_marker, find_marker_for_next_corner

track = load_track("data/tracks/sonoma.json")
nearest = find_nearest_marker(track, distance_m=350, kind="brake_ref")
# → MarkerDef(id="T2_bridge", label="the bridge", distance=414.0, ...)

best = find_marker_for_next_corner(track, distance_m=350, kind="brake_ref")
# Same as above but biased to markers attached to the upcoming corner first.
```

`build_context()` (now in `features/coaching/coach_engine.py` — a shim that re-exports from `features/coaching/engine_base.py`) automatically populates `CoachContext.next_brake_marker_label` and `next_apex_marker_label` from the upcoming corner's authored markers, so any coach that consumes `CoachContext` gets marker-aware phrasing for free.

`RuleCoach._render()` (in `features/coaching/rule_coach.py`) prefers marker labels when present:

- **Beginner**: `Turn 2 in 185 meters, brake at the bridge`
- **Intermediate**: `185, left 6, brake at the bridge, uphill`
- **Pro**: `Turn 2 185m, the bridge, apex 129`

---

## Future extensions

- **Marker GPS coordinates** — currently absent. The reference_line trace in the track JSON can be sampled at `marker.distance` to derive `(lat, lon)` for any marker. Useful for any map UI.
- **Marker thumbnails** — per-marker still images extracted from the synced VBO + dashcam video (`Sonoma Intermediate - 1_47.5.mp4`). See `docs/api.md` for the proposed `tools/extract_marker_thumbnails.py` pipeline.
- **Per-marker confidence + difficulty score** — combine corner severity with marker visibility (the bump is harder to use than the bridge); surface as a 1–6 score for the "pick 3 markers" UX.
- **Adaptive marker selection** — driver-level-specific marker choice (beginner sees "the bridge", pro sees "the second pavement crack").
