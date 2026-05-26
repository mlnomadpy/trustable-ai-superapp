#!/usr/bin/env bash
# Shared helpers for the deploy/phone/* ladder.
# `source` this from each step; never run it directly.

set -euo pipefail

# Colours for status messages (no-op when not a TTY).
if [ -t 1 ]; then
  C_OK=$'\033[32m';  C_WARN=$'\033[33m';  C_ERR=$'\033[31m'
  C_INFO=$'\033[36m'; C_DIM=$'\033[2m';   C_OFF=$'\033[0m'
else
  C_OK= C_WARN= C_ERR= C_INFO= C_DIM= C_OFF=
fi

say()  { printf "%s%s%s\n" "$C_INFO" "$*" "$C_OFF"; }
ok()   { printf "%s✓ %s%s\n" "$C_OK"  "$*" "$C_OFF"; }
warn() { printf "%s! %s%s\n" "$C_WARN" "$*" "$C_OFF" >&2; }
die()  { printf "%s✗ %s%s\n" "$C_ERR" "$*" "$C_OFF" >&2; exit 1; }
hr()   { printf "%s%s%s\n" "$C_DIM" "────────────────────────────────────────────────────────────" "$C_OFF"; }

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null || pwd)"
PHONE_HOME="/data/data/com.termux/files/home"
TERMUX_UID_DEFAULT=10312
TERMUX_UID="${TERMUX_UID:-$TERMUX_UID_DEFAULT}"
BRIDGE_PORT="${BRIDGE_PORT:-8765}"
PWA_PORT="${PWA_PORT:-5173}"
LOCALLLM_URL="${LOCALLLM_URL:-http://localhost:8080/v1}"
LOCALLLM_MODEL="${LOCALLLM_MODEL:-gemma-4-e2b}"

# Auto-detect adb serial. Honours $SERIAL if set.
detect_serial() {
  if [ -n "${SERIAL:-}" ]; then echo "$SERIAL"; return; fi
  local count
  count=$(adb devices | awk 'NR>1 && /device$/{c++} END{print c+0}')
  case "$count" in
    0) die "No adb device connected. Plug in over USB or 'adb connect <ip>:5555'.";;
    1) adb devices | awk 'NR>1 && /device$/{print $1; exit}';;
    *) die "Multiple adb devices found. Set SERIAL=<id> and re-run. Devices:\n$(adb devices | tail -n +2)";;
  esac
}

# Detect whether the phone has root (KernelSU/Magisk). Memoised in
# $_HAS_ROOT_CACHE so we only probe once per script invocation.
require_root() {
  local serial="${1:?serial required}"
  if [ -n "${_HAS_ROOT_CACHE:-}" ]; then
    [ "$_HAS_ROOT_CACHE" = "1" ] || die "$_NO_ROOT_MSG"
    return
  fi
  if adb -s "$serial" shell 'su root id 2>&1' 2>/dev/null | grep -q 'uid=0'; then
    export _HAS_ROOT_CACHE=1
    return
  fi
  export _HAS_ROOT_CACHE=0
  export _NO_ROOT_MSG="Step needs root (KernelSU or Magisk) to run as the Termux user.
This phone doesn't expose 'su'. Three options:
  1. Install KernelSU or Magisk (root the device) — the cleanest fix.
  2. Bootstrap SSH manually: open Termux app, run \`pkg install openssh && passwd && sshd\`,
     then re-run this script with SSH_PORT=8022 SSH_USER=u0_aXXX (see deploy/phone/README.md).
  3. Run Termux commands by hand: open the Termux app on the phone and execute the same
     command shown in the bridge log (deploy/phone/README.md → 'No-root manual install')."
  die "$_NO_ROOT_MSG"
}

# Run a bash command as the Termux user via adb shell + su (rooted phone).
# Uses base64 to bypass nested quoting hell.
termuxrun() {
  local serial="${1:?serial required}"; shift
  require_root "$serial"
  local cmd="$*"
  local b64
  b64=$(printf '%s' "$cmd" | base64)
  adb -s "$serial" shell "su $TERMUX_UID sh -c 'export PATH=/data/data/com.termux/files/usr/bin:/data/data/com.termux/files/usr/bin/applets HOME=$PHONE_HOME PREFIX=/data/data/com.termux/files/usr LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib TMPDIR=/data/data/com.termux/files/usr/tmp LANG=en_US.UTF-8; cd $PHONE_HOME; echo $b64 | base64 -d | bash'"
}

# Run a command as root via adb shell (KernelSU-style su root).
rootrun() {
  local serial="${1:?serial required}"; shift
  require_root "$serial"
  adb -s "$serial" shell "su root sh -c '$*'"
}

# Wait for /health to respond on the phone (over adb forward).
wait_for_bridge() {
  local serial="${1:?serial required}"
  local tries="${2:-20}"
  adb -s "$serial" forward "tcp:${BRIDGE_PORT}" "tcp:${BRIDGE_PORT}" >/dev/null 2>&1 || true
  for _ in $(seq 1 "$tries"); do
    if curl -sS -m 2 "http://127.0.0.1:${BRIDGE_PORT}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}
