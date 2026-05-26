# Pitwall on Termux — Foreground Service Setup

This directory contains everything needed to run `pitwall_bridge.py` on a
Pixel 10 via Termux as a managed foreground service that survives:

- screen-off (Wake Lock keeps the CPU alive)
- Doze + App Standby (Wake Lock + foreground notification)
- crashes (`runit` re-execs the process)
- reboots (Termux:Boot starts the supervisor on system boot)

The hardware setup it's designed for: Pixel mounted in-cabin, plugged into a
powered USB-C hub, with a USB-CAN adapter on `/dev/ttyACM0` reading the car's
OBD-II powertrain bus.

## One-time install on the Pixel

### Step 1 — Install Termux + add-ons

From [F-Droid](https://f-droid.org/) (the Play Store builds are deprecated as
of late 2024):

- **Termux** — the terminal itself
- **Termux:API** — exposes Android system APIs (TTS, notifications, wake-lock)
- **Termux:Boot** — runs scripts on system boot

Open Termux at least once after install so it provisions `$HOME`.

### Step 2 — Install packages

```bash
pkg update && pkg upgrade
pkg install python git termux-services termux-api openssh
pip install --upgrade flask duckdb requests python-can cantools
```

`termux-services` provides the runit-style `sv` supervisor used by the
service script in this repo.

### Step 3 — Clone the repo

```bash
git clone https://github.com/mlnomadpy/pitwall.git "$HOME/pitwall"
```

(Or `cp -r` from a USB-mounted laptop. Anywhere on the device works as long
as `$PITWALL_REPO` in the service `run` script points at it.)

### Step 4 — Wire the service

```bash
# Create the service directory under termux-services' watch path
ln -s "$HOME/pitwall/deploy/termux/service/pitwall-bridge" \
    "$PREFIX/var/service/pitwall-bridge"

# Make sure the run scripts are executable
chmod +x "$HOME/pitwall/deploy/termux/service/pitwall-bridge/run"
chmod +x "$HOME/pitwall/deploy/termux/service/pitwall-bridge/log/run"

# Enable the service so it auto-starts when the supervisor is running
sv-enable pitwall-bridge
```

### Step 5 — Wire the boot hook (optional but recommended)

```bash
mkdir -p "$HOME/.termux/boot"
cp "$HOME/pitwall/deploy/termux/boot/start-pitwall" "$HOME/.termux/boot/"
chmod +x "$HOME/.termux/boot/start-pitwall"
```

### Step 6 — Configure CAN (when ready)

The default service `run` script looks at the `PITWALL_CAN_CHANNEL` env var.
To turn on CAN ingest, drop a config file:

```bash
mkdir -p "$HOME/.config/pitwall"
cat > "$HOME/.config/pitwall/env" <<'EOF'
PITWALL_CAN_CHANNEL=/dev/ttyACM0
PITWALL_CAN_INTERFACE=slcan
PITWALL_CAN_BITRATE=500000
EOF
```

Then update the `run` script's preamble to source it:

```bash
# Insert near the top of deploy/termux/service/pitwall-bridge/run, just
# above "cd $PITWALL_REPO":
[ -f "$HOME/.config/pitwall/env" ] && . "$HOME/.config/pitwall/env"
```

(This keeps the CAN config out of git — handy if multiple devices use
different channels or you swap adapters.)

## Day-to-day operation

### Status

```bash
sv status pitwall-bridge
# run: pitwall-bridge: (pid 12345) 38542s; run: log: (pid 12346) 38542s
```

### Start / stop / restart

```bash
sv up pitwall-bridge
sv down pitwall-bridge
sv restart pitwall-bridge
```

### Live logs

```bash
tail -f $HOME/.pitwall-logs/current
```

Older logs land in the same directory as `@<timestamp>.s` — `svlogd`
rotates at 1 MB, keeps 10 historical files (about 10 MB total).

### Bridge health

From any browser (Pixel itself, or a laptop on the same Wi-Fi after running
`adb forward tcp:8765 tcp:8765`):

```
http://127.0.0.1:8765/health
```

A healthy response includes `coach`, `driver_level`, and `active_session_id`:

```json
{ "status": "ok", "version": "2.1", "engine": "sonic_model",
  "coach": "litert", "driver_level": "intermediate",
  "track": "Sonoma Raceway", "duckdb": true,
  "active_session_id": null, "timestamp": "..." }
```

## LocalLLM smoke check (ADR-022, pre-session)

Run this checklist on the Pixel **before every track day** to confirm the
LLM transport works end-to-end. Pitwall's default LLM transport is HTTP to
the [LocalLLM Android APK](https://www.tahabouhsine.com/localllm/) at
`http://127.0.0.1:8099/v1`. Two apps, one phone, one localhost hop.

### 1 — Verify LocalLLM is up and serving the expected model

```bash
# In Termux, after starting LocalLLM and downloading a Gemma 4 .litertlm:
curl -sS http://127.0.0.1:8099/v1/models | python3 -m json.tool
#  -> { "object": "list", "data": [ { "id": "gemma-4-e2b", ... } ] }
```

The default model id pitwall expects is `gemma3n-e2b` — override via
`PITWALL_ADK_OPENAI_MODEL=<id>` (legacy alias: `PITWALL_LITERT_MODEL`) to
match whatever LocalLLM has loaded. The LocalLLM model-id column in step 1
is the value to copy.

If `/v1/models` fails, open the LocalLLM app, pick a model from the in-app
Catalog, wait for the server indicator to turn green, then re-run.

**Critical: LocalLLM context window.** Pitwall's `/coach/brief` and
`/coach/debrief` prompts run ~3 000 characters (~900 tokens). LocalLLM's
default Gemma 4 context cap is sometimes pre-set to **256 tokens** in the
in-app Settings, which triggers a clean HTTP 500 from LocalLLM:

> `INVALID_ARGUMENT: Input token ids are too long. Exceeding the maximum
> number of tokens allowed: 892 >= 256`

Fix in LocalLLM → Settings → Model → "Max Input Tokens" ≥ 4096. Re-run
step 3 to confirm.

### 2 — Verify the bridge dials LocalLLM, not a stale lit-serve

```bash
# Confirm the env vars the bridge picks up
echo "URL=${PITWALL_ADK_OPENAI_URL:-$PITWALL_LITERT_URL}  MODEL=${PITWALL_ADK_OPENAI_MODEL:-$PITWALL_LITERT_MODEL}  BACKEND=$PITWALL_ADK_BACKEND"
# Empty values are fine — defaults are http://localhost:8099/v1 / gemma3n-e2b / openai.
# (Legacy PITWALL_LITERT_URL / PITWALL_LITERT_MODEL still work with a DeprecationWarning;
#  prefer the new PITWALL_ADK_OPENAI_* names for fresh deployments.)
```

### 3 — Round-trip a coach request through the bridge

```bash
# Pre-brief — exercises the warm path (LitertCoach.brief → POST /v1/chat/completions)
curl -sS "http://127.0.0.1:8765/coach/brief?driver=taha&focus=trail-brake" \
  | python3 -m json.tool | head -20
# Look for: { "narrative": "...prose...", "focus": [...], "emotion": "..." }
# A short literal "no LLM loaded" or empty narrative means the HTTP hop failed —
# check LocalLLM logs and the bridge's PITWALL_ADK_OPENAI_API_KEY (legacy:
# PITWALL_LITERT_API_KEY — must match LocalLLM → Settings → Bearer Token).

# Paddock Q&A — exercises ADK (Orchestrator → LiteLlm → LocalLLM)
curl -sS -X POST http://127.0.0.1:8765/coach/ask \
  -H 'Content-Type: application/json' \
  -d '{"driver_id":"taha","question":"hi"}' \
  | python3 -m json.tool | head -10
# Look for: { "answer": "<non-empty text>", "intent": "telemetry", ... }
```

### 4 — Watch one cue stream on a synthetic burst

```bash
# Subscribe (Ctrl-C to stop)
( curl -N "http://127.0.0.1:8765/cues/stream?session_id=smoke-001" & )
# In another shell, push a burst
curl -sS -X POST http://127.0.0.1:8765/analyze \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"smoke-001","burst_id":1,"avg_speed_kmh":110,"max_combo_g":1.2,"max_brake_bar":15,"avg_throttle_pct":50,"coast_frames":0,"trail_brake_frames":2,"frame_count":75,"corners_visited":["Turn 6"],"distance_m":1450,"in_corner":false}'
# Cue subscriber should receive one `data: {...}` event with `text` + `emotion`.
```

If all four checks pass, the LLM transport is healthy and you're ready to
drive. If any check fails, see [Troubleshooting](#troubleshooting).

## Verifying Doze survives

The Pixel's aggressive battery management is the real boss-fight here.
After install, do this 30-minute test:

1. `sv up pitwall-bridge`
2. Check `curl 127.0.0.1:8765/health` — should return 200
3. Lock the screen. Don't unlock it for 30 minutes. Walk away.
4. Come back, unlock, run the same `curl`. Still 200? You're good.
5. `tail -100 $HOME/.pitwall-logs/current` — should show the bridge has
   been quietly logging the whole time, not a 30-minute gap.

If step 5 shows a gap, Doze killed the process despite the wake lock.
That happens when:

- Termux:API package isn't installed (no `termux-wake-lock`)
- The Android **battery optimization** setting hasn't been disabled for
  Termux. Settings → Apps → Termux → Battery → **Unrestricted**.
- An OEM customisation is being aggressive (Pixel stock is mostly fine;
  Samsung One UI / Xiaomi MIUI are not — they may need additional
  whitelisting in the OEM's battery saver UI).

## Troubleshooting

| Symptom | Diagnosis |
|---|---|
| `sv status` says `down: ... unable to start` | Look at `$HOME/.pitwall-logs/current` for the python traceback. Usually a missing dep (`pip install python-can cantools`) or a wrong path in `run`. |
| Bridge starts but no CAN frames flow | `lsusb` (via `pkg install lsusb`) — confirm the adapter shows up. `ls -l /dev/ttyACM*` — confirm the device node exists. May need `chmod 666 /dev/ttyACM0` until `udev`-style rules are set up. |
| Wake-lock present but process still suspended | Termux must be excluded from battery optimisation in Android Settings. Then reboot. |
| `Termux:Boot` doesn't fire on reboot | The Termux:Boot app must be opened *at least once* after install before Android will trust it for boot intents. |
| Want to keep it screen-off but still browse | The PWA at `pitwall-web` opens normally; it talks to the bridge over `127.0.0.1:8765`. The bridge runs in the supervisor process, completely independent of any open Termux window. |

## Uninstall

```bash
sv-disable pitwall-bridge
rm "$PREFIX/var/service/pitwall-bridge"
rm -f "$HOME/.termux/boot/start-pitwall"
termux-wake-unlock
```

(Doesn't touch the repo or DuckDB — those stay where they are.)
