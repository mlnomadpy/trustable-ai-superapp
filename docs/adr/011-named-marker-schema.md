# ADR-011: Named-Marker Schema for Track Coaching

**Status:** Accepted
**Date:** 2026-04-28

## Context

The auto-built `data/tracks/sonoma.json` describes corners as `(entry, apex, exit)` distance triples plus `typical_brake_point.distance_before_entry`. This is geometrically correct but produces unnatural pace notes:

- "brake at 124 metres" — geometrically right, conversationally wrong.
- "Turn 6 in 80 m, BP 86 m, apex 77 km/h" — pure data, zero context.

The 2026-04-28 [Sonoma intelligence research](../sonoma_track_intelligence.md) found that **Sonoma's reference vocabulary is environmental, not numeric**. Pros call out the bridge over T2, the K-wall bend at T1, "the bump where the road widens left" before T11, the Toyota sign letters at T10, and the 300 board at T7. The Bentley 2018 coaching diary at Kanga Motorsports independently confirms this — Bentley used named landmarks ("the bumps in the carousel") and rate-of-change advice ("3 % more throttle"), not raw measurements.

We need a schema that lets the coach voice these landmarks instead of distances, without coupling Sonoma's idiosyncrasies into the coach engine.

## Decision

Each track JSON gains a `markers: []` array, both at the top level (flat, sorted by distance) and embedded under each corner. A marker is:

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

`kind` is a closed enum: `brake_ref | apex_ref | turn_in_ref | exit_ref | visual | nickname`.

`track_loader.MarkerDef` parses these into typed objects and exposes:

- `find_nearest_marker(track, distance, kind=, corner=, lookahead=)`
- `find_marker_for_next_corner(track, distance, kind="brake_ref")`

`coach_engine.CoachContext` carries `next_brake_marker_label`, `next_apex_marker_label`, `next_corner_tip`, and `next_corner_nickname`. `RuleCoach._render()` and any LLM coach prefer the marker label over the raw distance when one is present.

Marker authoring is done once per track via `tools/enrich_sonoma_track.py` which:
- Holds a single `ENRICHMENT` dict (one entry per corner).
- Materialises `distance` from `entry_distance + at_offset_m_from_entry` so the schema stays robust to track-builder geometry changes.
- Syncs to all four duplicate `sonoma.json` copies (`data/tracks/`, `src/pitwall/features/`, `flutter/assets/tracks/`, `flutter/android/app/src/main/assets/tracks/`).

## Consequences

**Positive**
- Pace notes sound native: 42 % of Sonoma pace notes per lap now reference a real landmark.
- The coach engine remains track-agnostic — no Sonoma-specific code paths. Adding Track 8 / Track 2 markers is just authoring data.
- Markers are self-documenting via `source`, `note`, and the per-marker `id` (stable identifier for future image / video associations).
- Per-corner `coaching_tip` and `nicknames` ride alongside markers and are available to any LLM coach for prompt enrichment.

**Negative**
- Hand-authored content must be kept in sync with the track. Mitigation: centralised `tools/enrich_sonoma_track.py` is idempotent and writes a `.bak` before mutating; the four duplicate copies are auto-synced from one canonical source.
- No GPS coordinates per marker yet — distance along track only. Mitigation: the reference_line trace in the track JSON can be sampled at `marker.distance` to derive `(lat, lon)` when a map UI lands. Documented in `docs/markers.md` as a future extension.
- Marker quality is bounded by the public sources we surveyed (Kanga, Blayze, lapmeta, Bentley). For tracks without similar coverage, fall back to numeric phrasing — already supported.

## Related

- [Markers reference](../markers.md)
- [Sonoma track intelligence](../sonoma_track_intelligence.md)
- [ADR-005 — Pedagogical Vector Retrieval](005-pedagogical-vectors.md) (markers complement, don't replace, pedagogical vectors)
- [ADR-012 — Coach Engine Adapter](012-coach-engine-adapter.md) (consumes `CoachContext.next_brake_marker_label`)
