#!/usr/bin/env bash
# Step 80 — launch Chrome on the phone pointed at the PWA.
# Optionally pass a sub-route: ./deploy/phone/80-open-pwa.sh /briefing
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

ROUTE="${1:-/}"
[[ "$ROUTE" = /* ]] || ROUTE="/$ROUTE"

hr
say "Step 80 — open PWA in phone Chrome"
hr
SERIAL=$(detect_serial)
URL="http://localhost:${PWA_PORT}${ROUTE}"

say "URL: $URL"
adb -s "$SERIAL" shell "am start -a android.intent.action.VIEW -d '$URL' \
  -n com.android.chrome/com.google.android.apps.chrome.Main" 2>&1 | tail -1

sleep 2
# Force-reload to bypass the PWA service worker cache when a new build landed
adb -s "$SERIAL" shell 'input keyevent KEYCODE_F5' >/dev/null 2>&1 || true

ok "Opened in Chrome. Use the fullscreen-toggle button in the corner to hide the URL bar."
hr
