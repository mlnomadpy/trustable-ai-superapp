#!/usr/bin/env bash
# Step 60 — wire the adb port bridges.
#   adb reverse :5173 → phone Chrome can reach Mac's PWA static server
#   adb forward :8765 → Mac can reach phone's pitwall bridge
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

hr
say "Step 60 — adb port wiring"
hr
SERIAL=$(detect_serial)

adb -s "$SERIAL" reverse "tcp:${PWA_PORT}" "tcp:${PWA_PORT}"
ok "phone:${PWA_PORT} ← Mac:${PWA_PORT}  (PWA reachable in phone Chrome)"

adb -s "$SERIAL" forward "tcp:${BRIDGE_PORT}" "tcp:${BRIDGE_PORT}"
ok "Mac:${BRIDGE_PORT} → phone:${BRIDGE_PORT}  (bridge curl/PWA testing from Mac)"

hr
ok "Port bridges live. Next: ./deploy/phone/70-start-bridge.sh"
