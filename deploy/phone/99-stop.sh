#!/usr/bin/env bash
# Step 99 — stop everything cleanly. Mac PWA server + phone bridge.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

hr
say "Stopping pitwall (PWA server + phone bridge)"
hr
SERIAL=$(detect_serial)

# 1. Phone bridge — only if root is available. Without it, this step is
#    a no-op (the user has to stop the bridge from the Termux app).
say "Stopping phone bridge…"
if adb -s "$SERIAL" shell 'su root id 2>&1' 2>/dev/null | grep -q 'uid=0'; then
  termuxrun "$SERIAL" '
    if [ -f ~/pitwall/data/bridge.pid ]; then
      kill -TERM $(cat ~/pitwall/data/bridge.pid) 2>/dev/null || true
    fi
    pkill -TERM -f "python -m pitwall" 2>/dev/null || true
    pkill -TERM -f "timeout " 2>/dev/null || true
    sleep 2
    if pgrep -f "python -m pitwall" >/dev/null 2>&1; then
      echo "  forcing SIGKILL"
      pkill -KILL -f "python -m pitwall" 2>/dev/null || true
    fi
    echo "remaining pitwall processes:"
    ps -ef | grep -E "python -m pitwall|timeout " | grep -v grep || echo "  (none)"
  '
  ok "Phone bridge stopped"
else
  warn "no root — skipping phone bridge stop (open Termux + 'pkill -f pitwall' manually)"
fi

# 2. Mac PWA server
say "Stopping Mac PWA serve…"
PIDS=$(lsof -ti :"$PWA_PORT" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  kill -9 $PIDS 2>/dev/null || true
  ok "killed pid(s): $PIDS"
else
  ok "(no serve process on :$PWA_PORT)"
fi

# 3. Tear down adb port bridges
adb -s "$SERIAL" reverse --remove "tcp:${PWA_PORT}" 2>/dev/null || true
adb -s "$SERIAL" forward --remove "tcp:${BRIDGE_PORT}" 2>/dev/null || true
ok "adb forwards removed"

hr
ok "Everything stopped."
