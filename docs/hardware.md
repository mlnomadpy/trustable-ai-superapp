# Hardware

Single-device architecture: a rooted Pixel 10 in cabin is the entire
compute stack. CAN telemetry comes from an AiM MXP dash logger, not
straight off the BMW PT-CAN.

```
┌───────────────────────────────────────────────────────────────────┐
│                           CAR                                      │
│                                                                    │
│   BMW E46 M3 ─────► AiM MXP ─────► CANable 2.0 ─USB-C OTG─► Pixel │
│   (MSS54HP DME)     (SmartyCam)    RH-02 PRO                  10   │
│                     v3.0 protocol  SLCAN @ 1 Mbit/s                │
│                                                                    │
│   Pixel 10 (Termux + KernelSU)                                     │
│     ├─ Python bridge :8765 (Flask + SQLite)                        │
│     ├─ LocalLLM APK :8080 (Gemma 4 E2B via LiteRT-LM)              │
│     └─ Chrome PWA (or any laptop via `adb reverse`)                │
└───────────────────────────────────────────────────────────────────┘
```

## Phone

| Item            | Detail                                                            |
| --------------- | ----------------------------------------------------------------- |
| Device          | Pixel 10 (codename `frankel`)                                     |
| Root            | KernelSU                                                          |
| Shell           | Termux + Termux:API (for fullscreen + storage access)             |
| SoC             | Tensor G5                                                         |
| Storage path    | `/data/data/com.termux/files/home/pitwall/`                       |

`/dev/ttyACM*` is `chmod 666`'d on bridge start so Termux can open the
CANable without `su` per frame — see `deploy/phone/70-start-bridge.sh`.

## CAN adapter — Jhoinrch CANable 2.0 RH-02 PRO

| Spec            | Value                                                             |
| --------------- | ----------------------------------------------------------------- |
| Transport       | USB-C OTG → `/dev/ttyACM0`                                        |
| Protocol        | SLCAN (ASCII), single-channel                                     |
| Bitrate         | **1 000 000 bit/s** (matches AiM MXP SmartyCam output)            |
| Frame format    | mixed standard (0x4xx) + extended IDs                             |
| python-can      | `--can-interface slcan --can-channel /dev/ttyACM0 --can-bitrate 1000000` |

## Dash logger — AiM MXP

The Pixel never touches the native BMW PT-CAN. The AiM MXP sits in the
middle: it ingests BMW DME/DSC (CANBUS1) plus TrailBrake TPMS (CANBUS2)
and re-broadcasts a fixed protocol on its SmartyCam output port. The
CANable listens to that output bus.

| Spec                  | Value                                                  |
| --------------------- | ------------------------------------------------------ |
| Make / Model          | AiM MXP                                                |
| Output port           | SmartyCam                                              |
| Protocol              | **AiM MXP SmartyCam Enhanced CAN Protocol v3.0**       |
| Software              | RaceStudio3 v3.83.00                                   |
| Total frames          | 20 (5 standard 0x420–0x424 + 15 extended 0x450–0x45E)  |
| Total channels        | 66                                                     |
| Input — CANBUS1       | BMW DME / DSC (BMW_MINI protocol, 500 Kbit/s, receive only) |
| Input — CANBUS2       | TrailBrake TPMS                                        |

Source spec PDF: `.context/CANable2_Pixel10_Developer_Integration_Spec_v3.0.pdf`.
On-bus frame layouts live in `data/dbc/pitwall.dbc`; the wrapping facts
(wiring, bitrate, broadcast rates, sign-recovery, known-broken channels)
live in `data/cars/bmw_e46_m3.yaml`.

### Known-broken channels (from live capture)

Gear position is not exposed by MSS54HP on any diagnostic path. MXP
slots at `0x420[4-5]` and `0x450[2-3]` read either `0` or `0xCFFE`
padding (PDF says 0; live capture shows `0xCFFE`). Coaches **derive gear
from RPM / wheel-speed ratio** rather than trusting these slots — see
`methods.gear_position` in the car YAML.

## Test vehicle

| Spec     | Value                                       |
| -------- | ------------------------------------------- |
| Make     | BMW                                         |
| Model    | M3                                          |
| Chassis  | E46                                         |
| Year     | 2003                                        |
| Engine   | S54B32                                      |
| ECU      | MSS54HP DME                                 |

## Field-test target

May 23, 2026 — Sonoma Raceway. Track JSON: `data/tracks/sonoma.json`.

## Audio

Pixel Earbuds (Bluetooth, passive isolation). The PWA's
`CoachVoiceButton` uses the Web Speech API for STT and `speechSynthesis`
for TTS; both run inside Chrome on the same phone — no separate audio
service.
