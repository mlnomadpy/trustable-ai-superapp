#!/usr/bin/env bash
# Step 00 — prerequisite check.
# Verifies you have adb, the phone is connected, Termux is installed,
# and root (KernelSU / Magisk) responds. Run this first on a fresh setup
# and any time something seems off.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

hr
say "Step 00 — prerequisite check"
hr

# 1. adb installed
if ! command -v adb >/dev/null 2>&1; then
  die "adb is not on PATH. Install with 'brew install --cask android-platform-tools' (macOS)."
fi
ok "adb installed: $(adb version | head -1)"

# 2. Phone connected
SERIAL=$(detect_serial)
ok "device: $SERIAL"

# 3. Android version
android_ver=$(adb -s "$SERIAL" shell getprop ro.build.version.release 2>/dev/null | tr -d '\r')
model=$(adb -s "$SERIAL" shell getprop ro.product.model 2>/dev/null | tr -d '\r')
ok "model: $model (Android $android_ver)"

# 4. Termux installed
if adb -s "$SERIAL" shell 'pm list packages com.termux' 2>/dev/null | grep -q com.termux; then
  ok "Termux installed (com.termux)"
else
  die "Termux is not installed. Install Termux + Termux:API from F-Droid first."
fi

# 5. Root access (KernelSU/Magisk needed for the file-staging step).
# Probe with `|| true` so set -e doesn't halt when su is missing.
set +e
root_probe=$(adb -s "$SERIAL" shell 'su root id 2>&1' 2>/dev/null)
set -e
if echo "$root_probe" | grep -q 'uid=0'; then
  ok "root (su) available"
  HAS_ROOT=1
else
  warn "root not detected — staging files into Termux home will need an alternative path."
  warn "Either install KernelSU/Magisk, OR run \`termux-setup-storage\` once inside Termux and we'll"
  warn "fall back to using /sdcard/Download as a transfer staging area."
  HAS_ROOT=0
fi

# 6. Termux UID — only meaningful if root works
if [ "$HAS_ROOT" = "1" ]; then
  uid=$(adb -s "$SERIAL" shell "su root sh -c 'stat -c %u /data/data/com.termux'" 2>/dev/null | tr -d '\r' || true)
  if [[ "$uid" =~ ^[0-9]+$ ]]; then
    ok "Termux uid: $uid (export TERMUX_UID=$uid to pin if it changes)"
  else
    warn "Could not read Termux uid — falling back to default $TERMUX_UID_DEFAULT"
  fi
else
  warn "Skipping Termux uid probe (no root)"
fi

# 7. USB-CAN adapter (optional, world-readable so no root needed)
set +e
acm=$(adb -s "$SERIAL" shell 'ls /dev/ttyACM* 2>/dev/null' 2>/dev/null | tr -d '\r')
set -e
if [ -n "$acm" ]; then
  ok "USB-CAN device(s) present: $acm"
else
  warn "No /dev/ttyACM* — fine if you only want to replay sessions; plug in the CANable for live CAN."
fi

# 8. LocalLLM (optional)
set +e
llm_pkg=$(adb -s "$SERIAL" shell 'pm list packages com.localllm.app' 2>/dev/null)
set -e
if echo "$llm_pkg" | grep -q localllm; then
  ok "LocalLLM app installed (start it manually + set 'Max Input Tokens' ≥ 1024)"
else
  warn "LocalLLM not installed — coach brief will fall back to honest empty state with error message"
fi

hr
ok "Prerequisites look good. Next: ./deploy/phone/10-termux-packages.sh"
