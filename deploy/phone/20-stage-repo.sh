#!/usr/bin/env bash
# Step 20 — stage the pitwall repo onto the phone.
# Tars the parts of the repo the bridge needs (src/, data/), pushes via
# adb, and extracts into ~/pitwall on the phone. Idempotent.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

hr
say "Step 20 — stage repo into Termux home"
hr
SERIAL=$(detect_serial)

# Build a tarball of just what the bridge needs. Skip caches + the big
# duckdb file (we'll stage that separately in step 40 if you want it).
# After the monorepo reorg the bridge package, its pyproject.toml, and
# the simulator all live under apps/. The phone script extracts and then
# (in step 30) installs from apps/bridge/.
TAR=/tmp/pitwall-src-$$.tgz
say "Building tarball at ${TAR}…"
tar -czf "$TAR" \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
  --exclude='node_modules' --exclude='*.duckdb' --exclude='*.duckdb.*' \
  -C "$REPO_ROOT" \
  apps/bridge apps/simulator data
ok "tarball: $(ls -lh "$TAR" | awk '{print $5}')"

say "Pushing to /data/local/tmp/…"
adb -s "$SERIAL" push "$TAR" /data/local/tmp/pitwall-src.tgz | tail -1

say "Extracting into ~/pitwall…"
termuxrun "$SERIAL" '
  mkdir -p ~/pitwall ~/pitwall/logs
  tar -xzf /data/local/tmp/pitwall-src.tgz -C ~/pitwall 2>/dev/null
  ls -la ~/pitwall | head -10
'
rm -f "$TAR"
adb -s "$SERIAL" shell 'rm -f /data/local/tmp/pitwall-src.tgz' >/dev/null 2>&1 || true

hr
ok "Repo staged at ~/pitwall on the phone. Next: ./deploy/phone/30-python-deps.sh"
