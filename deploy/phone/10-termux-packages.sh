#!/usr/bin/env bash
# Step 10 — install the Termux packages pitwall needs.
# Idempotent; safe to rerun. Takes ~2-5 min on first run.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

hr
say "Step 10 — install Termux packages"
hr
SERIAL=$(detect_serial)

# Mirror selection: pick a US mirror automatically (Termux's default
# selector sometimes hangs). Skip if user already configured one.
termuxrun "$SERIAL" '
  if [ ! -f $PREFIX/etc/apt/sources.list.d/_pitwall_mirror ]; then
    echo "deb https://mirror.fcix.net/termux/termux-main stable main" > $PREFIX/etc/apt/sources.list.d/_pitwall_mirror
  fi
  echo "--- pkg update ---"
  pkg update -y 2>&1 | tail -5
' >/dev/null 2>&1 || true

say "Installing core packages (python git clang make rust cmake ninja openssh termux-tools libduckdb)…"
termuxrun "$SERIAL" '
  pkg install -y \
    python git clang make pkg-config rust cmake ninja openssh termux-tools \
    libduckdb 2>&1 | tail -10
'

say "Verifying:"
termuxrun "$SERIAL" '
  python --version
  pip --version
  git --version
'

hr
ok "Termux packages installed. Next: ./deploy/phone/20-stage-repo.sh"
