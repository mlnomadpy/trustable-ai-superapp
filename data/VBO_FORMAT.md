# VBO File Format

The `.vbo` format is Racelogic's proprietary text-based telemetry format.

---

## Structure

```
File created on DD/MM/YYYY @ HH:MM:SS

[header]
signal_name_1
signal_name_2
...

[channel units]
unit_1
unit_2
...

[comments]
(c) Racelogic
<Unit Info>
Type   : VBVDHD2-V5 2cam
Serial : 005358
Firmware : 01.03.79.01
<GNSS>
Engine   : uBlox fw:3.010

[AVI]
VBOX0135_
mp4

[laptiming]
Start  +LLLLL.LLLLLL +LLLLL.LLLLLL +LLLLL.LLLLLL +LLLLL.LLLLLL ¬  Start / Finish

[column names]
sats time lat long velocity heading height vert-vel Tsample avifileindex avitime ...

[data]
140 163920.600 +2289.60462000 +7339.91306400 017.287 040.119 ...
140 163920.700 +2289.60480000 +7339.91311200 017.561 043.776 ...
```

## Sections

| Section | Content |
|---------|---------|
| `[header]` | Signal names, one per line. Describes the OBD/CAN channels appended after the built-in GPS/IMU columns. |
| `[channel units]` | Units for each OBD/CAN channel, one per line. Matches the order in `[header]`. |
| `[comments]` | Device metadata: type, serial number, firmware version, GNSS engine info, sync timestamps. |
| `[AVI]` | Associated video filename (without extension on first line, extension on second line). |
| `[laptiming]` | Start/finish line GPS coordinates in Racelogic internal format. 4 coordinates define a line across the track. |
| `[column names]` | Single line, space-separated. The actual column headers for the `[data]` section. This is the definitive column list. |
| `[data]` | Space-separated telemetry values. One row per sample. 10Hz (100ms per row). |

## Coordinate Format

Racelogic uses `DDMM.MMMMMMM` format (degrees × 100 + minutes):

```python
def vbo_to_decimal(value: float) -> float:
    """Convert VBO coordinate to decimal degrees."""
    degrees = int(value / 100)
    minutes = value - (degrees * 100)
    return degrees + minutes / 60.0

# Example: lat = 2289.60462 → 22° 89.60462' → 22 + 89.60462/60 = 23.493°
# Example: long = 7339.91306 → 73° 39.91306' → 73 + 39.91306/60 = 73.665°
# Note: longitude in this dataset is West, so negate: -73.665°
```

## Recording Device

| Property | Value |
|----------|-------|
| Device | Racelogic VBVDHD2-V5 2cam |
| Serial | 005358 |
| GPS rate | 20Hz (downsampled to 10Hz in VBO output) |
| GPS engine | uBlox |
| Sample period | 0.100s (10Hz) |
| CAN source | OBDLink MX via Bluetooth |
| Video | Dual camera, synced via `avitime` column |

## Parsing Notes

- All numeric values are space-separated. GPS coordinates use `+` prefix for positive values.
- Scientific notation is used for OBD/CAN values: `+2.980033E-01` = 0.298.
- The `[column names]` line is the source of truth for column ordering — it may differ slightly from `[header]` names (underscores vs spaces, abbreviated names).
- Some files have column names with parentheses: `Water_Temp_(Calc)`. Handle in your parser.
- Empty lines between sections are normal. Stop reading a section when you hit the next `[section]` header.
