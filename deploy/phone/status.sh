#!/usr/bin/env bash
# Status — print the live state of every layer. Safe to run anytime.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

hr
say "pitwall status"
hr

# 1. adb device
SERIAL=$(detect_serial)
ok "adb: $SERIAL"

# 2. Mac PWA serve
PWA_PIDS=$(lsof -ti :"$PWA_PORT" 2>/dev/null || true)
if [ -n "$PWA_PIDS" ]; then
  ok "Mac PWA serve on :$PWA_PORT  (pid $PWA_PIDS)"
else
  warn "Mac PWA serve on :$PWA_PORT  — not running"
fi

# 3. adb port wiring
REVERSE=$(adb -s "$SERIAL" reverse --list 2>/dev/null | grep ":$PWA_PORT" || true)
FORWARD=$(adb -s "$SERIAL" forward --list 2>/dev/null | grep ":$BRIDGE_PORT" || true)
[ -n "$REVERSE" ] && ok "adb reverse :$PWA_PORT  active" || warn "adb reverse :$PWA_PORT  not set up"
[ -n "$FORWARD" ] && ok "adb forward :$BRIDGE_PORT  active" || warn "adb forward :$BRIDGE_PORT  not set up"

# 4. Phone bridge — must respond AND return JSON (some random :8765
#    squatter could return HTML or a 404, which would crash json.load).
#    Redirect curl's diagnostic output to /dev/null so it doesn't leak
#    into our parsed http_code field.
health_resp=$(curl -s -m 3 -o /tmp/_status_body -w '%{http_code}|%{content_type}' "http://127.0.0.1:${BRIDGE_PORT}/health" 2>/dev/null || echo "000|")
http_code=$(echo "$health_resp" | cut -d'|' -f1)
content_type=$(echo "$health_resp" | cut -d'|' -f2)
if [ "$http_code" = "200" ] && [[ "$content_type" == *json* ]]; then
  python3 -c "
import sys, json
d = json.load(open('/tmp/_status_body'))
c = d.get('can') or {}
l = d.get('litert') or {}
print(f\"  status: {d.get('status')}\")
print(f\"  active_session_id: {d.get('active_session_id')}\")
print(f\"  track: {d.get('track')}\")
print(f\"  can.connected={c.get('connected')} fps={c.get('fps')} frames={c.get('frames_total')}\")
print(f\"  litert: up={l.get('up')} model={l.get('http_model')} url={l.get('http_url')}\")
" 2>/dev/null || warn "bridge returned 200 + json but failed to parse"
elif [ "$http_code" = "200" ]; then
  warn "phone bridge :$BRIDGE_PORT — something responded but not JSON (got $content_type). Stale squatter?"
elif [ "$http_code" = "000" ]; then
  warn "phone bridge :$BRIDGE_PORT — no response (forward not set up? bridge dead?)"
else
  warn "phone bridge :$BRIDGE_PORT — HTTP $http_code (expected 200)"
fi
rm -f /tmp/_status_body

# 5. Replay state — only if bridge looked healthy above
if [ "$http_code" = "200" ] && [[ "$content_type" == *json* ]]; then
  replay_code=$(curl -sS -m 3 -o /tmp/_replay_body -w '%{http_code}' "http://127.0.0.1:${BRIDGE_PORT}/session/replay/status" 2>&1 || echo "000")
  if [ "$replay_code" = "200" ]; then
    python3 -c "
import sys, json
d = json.load(open('/tmp/_replay_body'))
if d.get('running'):
    print(f\"  replay running: {d.get('source_session_id')} @ {d.get('speed')}x  {d.get('frame_idx')}/{d.get('total_frames')} ({d.get('elapsed_s'):.0f}s elapsed)\")
else:
    print('  replay: not running')
" 2>/dev/null || true
  fi
  rm -f /tmp/_replay_body
fi

hr
