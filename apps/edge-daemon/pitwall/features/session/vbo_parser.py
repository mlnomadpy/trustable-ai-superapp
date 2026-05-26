"""
VBO file parser for Racelogic data files.
Parses the proprietary .vbo format into structured telemetry frames.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VBOMetadata:
    """Header metadata parsed from a Racelogic .vbo file."""
    created: str = ""
    device_type: str = ""
    device_serial: str = ""
    firmware: str = ""
    columns: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)
    start_finish: object = None  # tuple of 4 floats or None
    sample_period: float = 0.1


@dataclass
class TelemetryFrame:
    """A single 10 Hz telemetry sample with all sensor channels."""
    timestamp: float
    lat: float          # decimal degrees
    lon: float          # decimal degrees
    speed: float        # m/s
    heading: float      # degrees
    altitude: float     # meters
    g_lat: float        # G
    g_long: float       # G
    combo_g: float      # combined G
    brake_pressure: float   # bar
    brake_position: float   # 0-1
    throttle: float     # 0-100%
    steering: float     # degrees
    rpm: float
    coolant_temp: float # C
    oil_temp: float     # C
    fuel_level: float   # %
    distance: float = 0.0       # cumulative meters
    distance_to_corner: float = 0.0
    corner_name: str = ""
    corner_severity: int = 0
    lap: int = 0
    lap_time: float = 0.0
    avitime: float = 0.0        # synced video time in seconds (from VBO avitime column)


def parse_vbo_coord(value: float) -> float:
    """Convert VBO deg*min format to decimal degrees.
    VBO stores as DDDMM.MMMMM (degrees * 100 + minutes).
    """
    degrees = int(value / 100)
    minutes = value - (degrees * 100)
    return degrees + minutes / 60.0


def parse_vbo(filepath: object) -> tuple[VBOMetadata, list[TelemetryFrame]]:
    """Parse a .vbo file into metadata and telemetry frames."""
    filepath = Path(filepath)
    lines = filepath.read_text(encoding="utf-8", errors="ignore").splitlines()

    meta = VBOMetadata()
    meta.created = lines[0] if lines else ""

    # Find sections
    sections = {}
    for i, line in enumerate(lines):
        if line.strip().startswith("[") and line.strip().endswith("]"):
            sections[line.strip().strip("[]")] = i

    # Parse header (column definitions)
    if "header" in sections:
        start = sections["header"] + 1
        end = sections.get("channel units", len(lines))
        header_lines = [l.strip() for l in lines[start:end] if l.strip() and not l.strip().startswith("[")]
        meta.columns = header_lines  # not used directly, column names come from [column names]

    # Parse column names
    if "column names" in sections:
        col_line = lines[sections["column names"] + 1].strip()
        meta.columns = col_line.split()

    # Parse channel units
    if "channel units" in sections:
        start = sections["channel units"] + 1
        end = min(start + 50, len(lines))
        meta.units = []
        for line in lines[start:end]:
            if line.strip().startswith("["):
                break
            if line.strip():
                meta.units.append(line.strip())

    # Parse lap timing (start/finish line)
    if "laptiming" in sections:
        lap_line = lines[sections["laptiming"] + 1].strip()
        coords = re.findall(r"[+-]?\d+\.\d+", lap_line)
        if len(coords) >= 4:
            meta.start_finish = tuple(float(c) for c in coords[:4])

    # Parse comments for device info
    if "comments" in sections:
        start = sections["comments"] + 1
        for line in lines[start:start + 20]:
            if "Type" in line:
                meta.device_type = line.split(":")[-1].strip()
            elif "Serial" in line:
                meta.device_serial = line.split(":")[-1].strip()
            elif "Firmware" in line:
                meta.firmware = line.split(":")[-1].strip()

    # Parse data
    if "data" not in sections:
        return meta, []

    data_start = sections["data"] + 1
    col_names = meta.columns
    frames = []
    cumulative_distance = 0.0
    prev_lat = None
    prev_lon = None

    for line in lines[data_start:]:
        line = line.strip()
        if not line or line.startswith("["):
            break

        parts = line.split()
        if len(parts) != len(col_names):
            continue

        row = {}
        for j, col in enumerate(col_names):
            try:
                row[col] = float(parts[j])
            except ValueError:
                row[col] = 0.0

        # Convert coordinates
        lat = parse_vbo_coord(abs(row.get("lat", 0)))
        lon = -parse_vbo_coord(abs(row.get("long", 0)))  # West is negative

        # Compute cumulative distance
        if prev_lat is not None:
            import math
            dlat = math.radians(lat - prev_lat)
            dlon = math.radians(lon - prev_lon)
            a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(prev_lat)) * math.cos(math.radians(lat)) * math.sin(dlon / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            cumulative_distance += 6371000 * c  # meters

        prev_lat = lat
        prev_lon = lon

        frame = TelemetryFrame(
            timestamp=row.get("time", 0),
            lat=lat,
            lon=lon,
            speed=row.get("velocity", 0) / 3.6,  # km/h to m/s
            heading=row.get("heading", 0),
            altitude=row.get("height", 0),
            g_lat=row.get("Indicated_Lateral_Acceleration", 0),
            g_long=row.get("Indicated_Longitudinal_Acceleration", 0),
            combo_g=row.get("ComboAcc", 0),
            brake_pressure=row.get("Brake_Pressure", 0),
            brake_position=row.get("Brake_Position", 0),
            throttle=row.get("Throttle_Position", 0),
            steering=row.get("Steering_Angle", 0),
            rpm=row.get("Engine_Speed", 0),
            coolant_temp=row.get("Coolant_Temperature", 0),
            oil_temp=row.get("Oil_Temperature", 0),
            fuel_level=row.get("Fuel_Level", 0),
            distance=cumulative_distance,
            avitime=row.get("avitime", 0),
        )
        frames.append(frame)

    return meta, frames
