#!/usr/bin/env bash
# Step 50 — build the PWA on the Mac and start a local static server.
# The server keeps running in the background; PWA is reached from the
# phone via 'adb reverse tcp:5173 tcp:5173' (set up in step 60).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

hr
say "Step 50 — build PWA + serve from Mac"
hr
PWA_DIR="$REPO_ROOT/apps/pwa"

if ! command -v node >/dev/null 2>&1; then
  die "node not on PATH. Install via 'brew install node' (macOS) or https://nodejs.org"
fi
ok "node: $(node -v)"

cd "$PWA_DIR"
if [ ! -d node_modules ]; then
  say "First-time install (npm install)…"
  npm install 2>&1 | tail -3
fi

say "Building dist…"
npm run build 2>&1 | tail -3

# Tear down any previous serve on the port
EXISTING=$(lsof -ti :"$PWA_PORT" 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
  warn "Port $PWA_PORT in use by pid $EXISTING — killing"
  kill -9 $EXISTING 2>/dev/null || true
  sleep 1
fi

say "Starting npx serve on :${PWA_PORT}…"
nohup npx serve -s dist -l "tcp://127.0.0.1:${PWA_PORT}" \
  > /tmp/pwa-serve.log 2>&1 &
SERVE_PID=$!
ok "serve pid=$SERVE_PID  log=/tmp/pwa-serve.log"

# npx-serve takes 1-5 s to bind; poll up to 10 s for the HTTP check.
HTTP="000"
for _ in $(seq 1 20); do
  if ! kill -0 "$SERVE_PID" 2>/dev/null; then
    die "serve died — check /tmp/pwa-serve.log"
  fi
  HTTP=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PWA_PORT}/" 2>/dev/null || echo "000")
  if [ "$HTTP" = "200" ]; then break; fi
  sleep 0.5
done

if [ "$HTTP" = "200" ]; then
  ok "http://127.0.0.1:${PWA_PORT}/ → 200"
else
  warn "http://127.0.0.1:${PWA_PORT}/ → $HTTP after 10 s — check /tmp/pwa-serve.log"
fi

hr
ok "PWA built + served. Next: ./deploy/phone/60-forward-ports.sh"
