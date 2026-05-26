#!/usr/bin/env bash
# Step 70 — start the pitwall bridge on the phone (as a daemon under
# `timeout 3600` so it auto-stops after an hour). Auto-detects an
# attached CANable on /dev/ttyACM*; without one, runs in "no live CAN"
# mode and you drive telemetry via /session/replay/*.
#
# Env knobs (export before running):
#   DURATION_S            bridge auto-stop (default 3600 = 1 h)
#   NO_CAN=1              skip CAN reader even if /dev/ttyACM* exists
#   SIM=1                 enable the built-in AiM MXP synthetic simulator
#                         (mutually exclusive with live CAN; forces NO_CAN)
#   SIM_SPEED=1.0         simulator wall-clock speed multiplier
#   SIM_LAP_SECONDS=60    duration of one synthetic lap (default 60 s)
#   LOCALLLM_URL          default http://localhost:8080/v1
#   LOCALLLM_MODEL        default gemma-4-e2b
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

hr
say "Step 70 — start pitwall bridge"
hr
SERIAL=$(detect_serial)
DURATION_S="${DURATION_S:-3600}"

# Pick mode: SIM (synthetic) > NO_CAN (idle) > live CAN auto-detect.
CAN_ARGS=""
if [ "${SIM:-0}" = "1" ]; then
  SIM_SPEED="${SIM_SPEED:-1.0}"
  SIM_LAP_SECONDS="${SIM_LAP_SECONDS:-60}"
  ok "SIM=1 — built-in AiM MXP synthetic simulator (speed=${SIM_SPEED}, lap=${SIM_LAP_SECONDS}s)"
  CAN_ARGS="--simulate --simulate-speed ${SIM_SPEED} --simulate-lap-seconds ${SIM_LAP_SECONDS}"
elif [ "${NO_CAN:-0}" != "1" ]; then
  DEV=$(adb -s "$SERIAL" shell 'ls /dev/ttyACM* 2>/dev/null | head -1' | tr -d '\r')
  if [ -n "$DEV" ]; then
    # chmod 666 so Termux can open it without root each frame
    adb -s "$SERIAL" shell "su root chmod 666 $DEV" >/dev/null 2>&1 || true
    ok "CAN device: $DEV"
    CAN_ARGS="--can-interface slcan --can-channel $DEV --can-bitrate 1000000"
  else
    warn "no /dev/ttyACM* — bridge will start without live CAN; use SIM=1 or /session/replay/start"
  fi
else
  warn "NO_CAN=1 — skipping CAN reader; bridge will start in replay-only mode"
fi

say "Killing any old bridge process…"
termuxrun "$SERIAL" 'pkill -f "python -m pitwall" 2>/dev/null; pkill -f "timeout " 2>/dev/null; sleep 1; true'

CMD="cd ~/pitwall && . .venv/bin/activate
nohup env \
  PITWALL_ADK_OPENAI_URL=${LOCALLLM_URL} \
  PITWALL_ADK_OPENAI_MODEL=${LOCALLLM_MODEL} \
  PITWALL_ADK_OPENAI_API_KEY=local \
  PITWALL_LLM_MAX_TOKENS=512 \
  PITWALL_COMPACT_PROMPTS=1 \
  PYTHONPATH=apps/bridge \
  timeout ${DURATION_S} python -m pitwall ${CAN_ARGS} \
    --can-car-config data/cars/bmw_e46_m3.yaml \
    --can-dbc data/dbc/pitwall.dbc \
    --track data/tracks/sonoma.json \
    --port ${BRIDGE_PORT} --log-level INFO \
    > logs/bridge.log 2>&1 &
echo \$! > data/bridge.pid
echo bridge_pid=\$!"

termuxrun "$SERIAL" "$CMD"
say "Waiting for /health …"
if wait_for_bridge "$SERIAL" 15; then
  ok "bridge up"
  curl -sS "http://127.0.0.1:${BRIDGE_PORT}/health" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);c=d.get('can') or {};print(f\"  active_session={d.get('active_session_id')}  track={d.get('track')}  can.connected={c.get('connected')} fps={c.get('fps')}\")"
else
  die "bridge didn't respond on /health within 15 s — see logs/bridge.log on phone"
fi

hr
ok "Bridge running for ${DURATION_S}s. Next: ./deploy/phone/80-open-pwa.sh"
ok "Tail logs:  adb -s $SERIAL shell 'su $TERMUX_UID tail -f $PHONE_HOME/pitwall/logs/bridge.log'"
