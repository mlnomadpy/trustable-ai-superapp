"""
Track Loader — loads track.json files and provides runtime corner/sector lookup.
Replaces the hardcoded track_map.py with data-driven track definitions.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MarkerDef:
    """A named visual / brake / apex reference point on the track.

    `kind` is one of "brake_ref", "apex_ref", "turn_in_ref", "exit_ref",
    "visual", "nickname". `distance` is the cumulative track distance in
    metres. `corner` is the canonical corner name this marker belongs to.
    """
    id: str
    kind: str
    label: str
    distance: float
    corner: str
    source: str = ""
    note: str = ""


@dataclass
class CornerDef:
    """Full definition of a track corner — geometry, speed profiles, and coaching data."""
    name: str
    number: int
    direction: str
    severity: int
    entry_distance: float
    apex_distance: float
    exit_distance: float
    curvature_peak: float
    entry_speed: float      # m/s
    apex_speed: float       # m/s
    exit_speed: float       # m/s
    brake_distance: float   # meters before entry where braking starts
    brake_pressure: float   # typical peak bar
    elevation_change: float # meters
    nicknames: list[str] = None
    coaching_tip: str = ""
    markers: list[MarkerDef] = None


@dataclass
class SectorDef:
    """A track sector defined by start and end cumulative distances."""
    name: str
    start_distance: float
    end_distance: float


@dataclass
class TrackMap:
    """Complete runtime track model loaded from a track.json file."""
    name: str
    track_length: float
    sf_lat: float
    sf_lon: float
    sf_heading: float
    corners: list[CornerDef]
    sectors: list[SectorDef]
    elevation_profile: list[tuple[float, float]]  # (distance, altitude)
    reference_line: list[tuple[float, float, float]]  # (distance, lat, lon)
    markers: list[MarkerDef] = None
    intel_notes: dict = None


def _markers_from_corner(c: dict) -> list[MarkerDef]:
    out = []
    for m in c.get("markers", []) or []:
        out.append(MarkerDef(
            id=m.get("id", ""),
            kind=m.get("kind", "visual"),
            label=m.get("label", ""),
            distance=float(m.get("distance", 0)),
            corner=m.get("corner", c.get("name", "")),
            source=m.get("source", ""),
            note=m.get("note", ""),
        ))
    return out


def load_track(path: object) -> TrackMap:
    """Load a track.json into a TrackMap for runtime use."""
    with open(path) as f:
        data = json.load(f)

    corners = []
    for c in data.get("corners", []):
        spd = c.get("typical_speed_ms", {})
        brk = c.get("typical_brake_point", {})
        corners.append(CornerDef(
            name=c["name"],
            number=c["number"],
            direction=c["direction"],
            severity=c["severity"],
            entry_distance=c["entry"]["distance"],
            apex_distance=c["apex"]["distance"],
            exit_distance=c["exit"]["distance"],
            curvature_peak=c.get("curvature_peak", 0),
            entry_speed=spd.get("entry", 0),
            apex_speed=spd.get("apex", 0),
            exit_speed=spd.get("exit", 0),
            brake_distance=brk.get("distance_before_entry", 0),
            brake_pressure=brk.get("pressure_bar", 0),
            elevation_change=c.get("elevation_change_m", 0),
            nicknames=c.get("nicknames", []) or [],
            coaching_tip=c.get("coaching_tip", "") or "",
            markers=_markers_from_corner(c),
        ))

    sectors = []
    for s in data.get("sectors", []):
        sectors.append(SectorDef(
            name=s["name"],
            start_distance=s["start_distance"],
            end_distance=s["end_distance"],
        ))

    sf = data.get("start_finish", {})
    elev = [(e["distance"], e["altitude"]) for e in data.get("elevation_profile", [])]
    ref = [(r["distance"], r["lat"], r["lon"]) for r in data.get("reference_line", [])]

    # Flat markers list (top-level array in JSON; falls back to flattening corners)
    flat_markers = []
    if isinstance(data.get("markers"), list):
        for m in data["markers"]:
            flat_markers.append(MarkerDef(
                id=m.get("id", ""),
                kind=m.get("kind", "visual"),
                label=m.get("label", ""),
                distance=float(m.get("distance", 0)),
                corner=m.get("corner", ""),
                source=m.get("source", ""),
                note=m.get("note", ""),
            ))
    else:
        for c in corners:
            flat_markers.extend(c.markers or [])
    flat_markers.sort(key=lambda m: m.distance)

    return TrackMap(
        name=data.get("name", "Unknown"),
        track_length=data.get("track_length_m", 0),
        sf_lat=sf.get("lat", 0),
        sf_lon=sf.get("lon", 0),
        sf_heading=sf.get("heading", 0),
        corners=corners,
        sectors=sectors,
        elevation_profile=elev,
        reference_line=ref,
        markers=flat_markers,
        intel_notes=data.get("intel_notes", {}) or {},
    )


def find_nearest_corner(track: TrackMap, distance: float, lookahead: float = 500.0) -> object:
    """Find the next corner within lookahead distance."""
    track_dist = distance % track.track_length
    best = None
    best_gap = float("inf")

    for corner in track.corners:
        gap = (corner.entry_distance - track_dist) % track.track_length
        if 0 < gap < lookahead and gap < best_gap:
            best = corner
            best_gap = gap

    return best


def distance_to_corner(track: TrackMap, distance: float, corner: CornerDef) -> float:
    """Distance from current position to corner entry."""
    track_dist = distance % track.track_length
    return (corner.entry_distance - track_dist) % track.track_length


def is_in_corner(track: TrackMap, distance: float) -> object:
    """Check if current distance is inside any corner."""
    track_dist = distance % track.track_length
    for corner in track.corners:
        if corner.entry_distance <= track_dist <= corner.exit_distance:
            return corner
    return None


def is_past_apex(track: TrackMap, distance: float) -> object:
    """Check if we're past the apex of a corner (exit phase)."""
    track_dist = distance % track.track_length
    for corner in track.corners:
        if corner.apex_distance < track_dist <= corner.exit_distance:
            return corner
    return None


def get_sector(track: TrackMap, distance: float) -> object:
    """Get the sector for the current distance."""
    track_dist = distance % track.track_length
    for sector in track.sectors:
        if sector.start_distance <= track_dist < sector.end_distance:
            return sector
    return None


def get_elevation(track: TrackMap, distance: float) -> float:
    """Interpolate altitude at a given distance."""
    track_dist = distance % track.track_length
    if not track.elevation_profile:
        return 0.0

    # Find surrounding points
    for i in range(len(track.elevation_profile) - 1):
        d1, a1 = track.elevation_profile[i]
        d2, a2 = track.elevation_profile[i + 1]
        if d1 <= track_dist <= d2:
            t = (track_dist - d1) / (d2 - d1) if d2 > d1 else 0
            return a1 + t * (a2 - a1)

    return track.elevation_profile[-1][1]


def get_reference_position(track: TrackMap, distance: float) -> object:
    """Get the reference line lat/lon at a given distance (for cross-track error)."""
    track_dist = distance % track.track_length
    if not track.reference_line:
        return None

    for i in range(len(track.reference_line) - 1):
        d1, lat1, lon1 = track.reference_line[i]
        d2, lat2, lon2 = track.reference_line[i + 1]
        if d1 <= track_dist <= d2:
            t = (track_dist - d1) / (d2 - d1) if d2 > d1 else 0
            return (lat1 + t * (lat2 - lat1), lon1 + t * (lon2 - lon1))

    d, lat, lon = track.reference_line[-1]
    return (lat, lon)


def find_nearest_marker(
    track: TrackMap,
    distance: float,
    *,
    kind: str = None,
    corner: str = None,
    lookahead: float = 250.0,
) -> object:
    """Find the next marker within `lookahead` metres ahead of the car.

    `kind` filters by marker kind (e.g. "brake_ref"). `corner` filters to
    markers attached to a specific corner name (e.g. "Turn 11"). Returns
    None when nothing matches.
    """
    if not track.markers:
        return None
    track_dist = distance % track.track_length if track.track_length else distance
    best = None
    best_gap = float("inf")
    for m in track.markers:
        if kind and m.kind != kind:
            continue
        if corner and m.corner != corner:
            continue
        gap = (m.distance - track_dist) % track.track_length if track.track_length else m.distance - track_dist
        # gap=0 means the marker is right at the car's position — accept it
        if 0 <= gap < lookahead and gap < best_gap:
            best = m
            best_gap = gap
    return best


def find_marker_for_next_corner(
    track: TrackMap,
    distance: float,
    *,
    kind: str = "brake_ref",
    lookahead: float = 250.0,
) -> object:
    """Convenience: pick the most relevant marker for the upcoming corner.

    Walks through corners in lookahead range and returns the closest marker
    of the requested kind belonging to that corner. Falls back to any marker
    of `kind` within `lookahead` if no corner-attached one is found.
    """
    nxt = find_nearest_corner(track, distance, lookahead=lookahead)
    if nxt is not None:
        m = find_nearest_marker(track, distance, kind=kind, corner=nxt.name, lookahead=lookahead)
        if m is not None:
            return m
    return find_nearest_marker(track, distance, kind=kind, lookahead=lookahead)


def cross_track_error(track: TrackMap, distance: float, lat: float, lon: float) -> float:
    """Compute lateral offset from the reference line in meters."""
    ref = get_reference_position(track, distance)
    if ref is None:
        return 0.0

    ref_lat, ref_lon = ref
    R = 6371000
    dlat = math.radians(lat - ref_lat)
    dlon = math.radians(lon - ref_lon)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(ref_lat)) * math.cos(math.radians(lat)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
