# `deploy/phone/` — operator's guide

Thirteen scripts to take a fresh Pixel from "nothing installed" to "bridge
serving SSE under live CAN, PWA running, replay endpoints live". Read the
script source for ground truth — this README is a fingerpost.

## The ladder

| Script | Needs root? | One-line |
|---|---|---|
| `00-check.sh`            | No  | Verify `adb`, Termux user, root, USB-CAN, LocalLLM. Prints a go/no-go for every dependency. |
| `10-termux-packages.sh`  | Yes | `pkg install` Python 3.13, git, clang, build deps, `python-pyarrow`, `python-numpy`. SQLite ships with Termux. |
| `20-stage-repo.sh`       | Yes | `tar` `apps/bridge + apps/simulator + data/`, `adb push`, extract into `~/pitwall` on the phone. |
| `30-python-deps.sh`      | Yes | Create `~/pitwall/.venv`, `pip install` runtime deps, drop the `termux_system.pth` shim so pyarrow + numpy resolve from Termux's system site-packages. |
| `40-stage-recording.sh`  | Yes | (Optional) push a `.sqlite` recording for replay. |
| `50-build-pwa.sh`        | No  | `npm install && npm run build && npx serve -s apps/pwa/dist -l :5173` on the **Mac**. |
| `60-forward-ports.sh`    | No  | `adb reverse tcp:5173 tcp:5173` + `adb forward tcp:8765 tcp:8765`. |
| `70-start-bridge.sh`     | Yes | Start the bridge under `timeout`. See env knobs below. |
| `80-open-pwa.sh`         | No  | Launch Chrome on the phone at `http://localhost:5173`. |
| `99-stop.sh`             | Mixed | Stop everything cleanly (Mac PWA, phone bridge, port mappings). |
| `_common.sh`             | —   | Sourced helpers; never run directly. |
| `status.sh`              | No  | Single-screen status of every layer. |

## Daily run

```bash
./deploy/phone/50-build-pwa.sh
./deploy/phone/60-forward-ports.sh
./deploy/phone/70-start-bridge.sh
./deploy/phone/80-open-pwa.sh /briefing
# … drive …
./deploy/phone/99-stop.sh
```

Code change → only `20-stage-repo.sh && 70-start-bridge.sh` again. PWA-only
change → only `50-build-pwa.sh && 80-open-pwa.sh` (F5 to bypass SW cache).

## `70-start-bridge.sh` env knobs

All optional; export before running.

| Knob | Default | What it does |
|---|---|---|
| `DURATION_S`        | `3600`                       | Wraps the bridge in `timeout ${DURATION_S}` so it self-stops after an hour. Override for long sessions. |
| `NO_CAN`            | unset                        | `NO_CAN=1` skips the CAN reader even if `/dev/ttyACM*` is attached. Use for replay-only sessions. |
| `SIM`               | unset                        | `SIM=1` enables the built-in AiM MXP synthetic simulator. Forces `NO_CAN` (one publisher). |
| `SIM_SPEED`         | `1.0`                        | Simulator wall-clock multiplier. |
| `SIM_LAP_SECONDS`   | `60`                         | Duration of one synthetic lap. |
| `LOCALLLM_URL`      | `http://localhost:8080/v1`   | Exported as `PITWALL_ADK_OPENAI_URL`; LocalLLM's OpenAI-compat base. |
| `LOCALLLM_MODEL`    | `gemma-4-e2b`                | Exported as `PITWALL_ADK_OPENAI_MODEL`; must match what LocalLLM has loaded. |
| `BRIDGE_PORT`       | `8765`                       | Bridge HTTP port. |
| `SERIAL`            | auto-detected                | Pin a specific adb device. Required when more than one device is attached. |
| `TERMUX_UID`        | `10312`                      | The `su <uid>` target for `termuxrun()`. Override only if your Termux runs under a different uid. |

`70-start-bridge.sh` itself decides CAN mode by precedence: `SIM=1` >
`NO_CAN=1` > auto-detect `/dev/ttyACM*`. When a CANable is found it's
`chmod 666`-d as root so the bridge can open it without re-rooting per
frame. Three more env vars are always exported into the bridge process:

- `PITWALL_ADK_OPENAI_API_KEY=local`  (LocalLLM accepts any bearer)
- `PITWALL_LLM_MAX_TOKENS=512`
- `PITWALL_COMPACT_PROMPTS=1`         (Gemma-4-E2B context fit)

## `_common.sh` helpers

Sourced by every other script. Highlights:

- **`detect_serial`** — picks the only attached adb device, honours
  `$SERIAL` when set, dies with a clear message if zero or more than one.
- **`require_root <serial>`** — probes `su root id`, memoises the result.
  On failure prints the three escape hatches (KernelSU/Magisk, SSH
  bootstrap, manual Termux install).
- **`termuxrun <serial> <cmd>`** — base64-pipes `<cmd>` into
  `adb shell su <uid> sh -c …` with `PATH`, `HOME`, `PREFIX`,
  `LD_LIBRARY_PATH`, `TMPDIR`, `LANG` already exported. Without these
  exports Termux-built binaries can't find their `.so` files.
- **`rootrun <serial> <cmd>`** — same idea via `su root`. Used for
  one-off privileged ops like `chmod 666 /dev/ttyACM0`.
- **`wait_for_bridge <serial> [tries]`** — `adb forward` + poll
  `/health` over HTTP. Returns 0 the moment the bridge responds.

## `status.sh` sample output

```
────────────────────────────────────────────────────────────
pitwall status
────────────────────────────────────────────────────────────
✓ adb: 53061FDCR000XR
✓ Mac PWA serve on :5173  (pid 84931)
✓ adb reverse :5173  active
✓ adb forward :8765  active
  status: ok
  active_session_id: sonoma_2026-05-26T14-12-08
  track: Sonoma Raceway
  can.connected=true fps=84.0 frames=412877
  litert: up=true model=gemma-4-e2b url=http://localhost:8080/v1
  replay: not running
────────────────────────────────────────────────────────────
```

Lines flip to a yellow `!` when a layer is missing. The `/health` parse
is JSON-aware — a stale `:8765` squatter that returns HTML gets called
out instead of pretending it's the bridge.

## Troubleshooting

**Phone DNS broken inside `adb shell su <uid>`** (so `pip install` /
`pkg update` fail with "Temporary failure in name resolution"). Known
issue on this Pixel. Workarounds: drive `pkg update` from the Termux
app's own UI; `pip install` from pre-staged wheels (see `~/adk-wheels/`
for the ADK case). `00-check.sh` will warn if it detects this state.

**No `/dev/ttyACM*` showing up.** Either the CANable isn't plugged in,
USB-OTG mode isn't on, or root hasn't approved the `chmod`. Re-run
`70-start-bridge.sh` with `NO_CAN=1` to get the bridge up regardless,
then unplug + replug the CANable and `adb shell ls /dev/ttyACM*` to
confirm it's enumerated.

**LocalLLM not running.** `/health.litert.up == false` in `status.sh`.
Open the LocalLLM app on the phone, confirm a model is loaded, confirm
the in-app HTTP server toggle is on. The bridge will still start; brief/
debrief endpoints will return `narrative_md: ""` with `error:
"engine_not_loaded"` until LocalLLM is back.

**pyarrow not loadable.** `python -c 'import pyarrow'` fails inside the
venv. The `termux_system.pth` shim is missing — re-run
`30-python-deps.sh`. Verify with `ls
~/pitwall/.venv/lib/python3.13/site-packages/termux_system.pth`.

**Bridge dies on start.** `tail ~/pitwall/logs/bridge.log` on the phone:

```bash
adb -s "$SERIAL" shell "su 10312 tail -50 /data/data/com.termux/files/home/pitwall/logs/bridge.log"
```

Common causes: `--can-channel /dev/ttyACMX` (wrong device path),
`signal_registry` migration not applied (re-run `30-python-deps.sh` to
re-create the DB), port `:8765` already in use (kill the stale process
via `99-stop.sh`).

## What does NOT live in this repo

- Termux + Termux:API APKs — install from F-Droid before step 00.
- LocalLLM Android APK + the `gemma-4-e2b` `.litertlm` — install and
  load in-app.

## Logs

| What | Path |
|---|---|
| Mac PWA serve    | `/tmp/pwa-serve.log` |
| Phone bridge     | `~/pitwall/logs/bridge.log` (on the phone) |
| PID file         | `~/pitwall/data/bridge.pid` |
| Recordings stash | `~/pitwall/data/archive/` |

## Root requirement

Steps **10, 20, 30, 40, 70** drop into the Termux user (uid 10312+) via
`su`. The cleanest path is KernelSU or Magisk; `_common.sh:require_root`
prints SSH-bootstrap and manual fallbacks when root is missing.

Steps **00, 50, 60, 80, 99, status** never need root.
