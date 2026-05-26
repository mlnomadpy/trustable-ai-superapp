#!/usr/bin/env bash
# Step 40 — OPTIONAL — push a recorded session onto the phone so you can
# replay it through the bridge instead of needing live CAN.
# By default pushes the prepared 23-min Sonoma session at
# .context/recordings/track-sonoma-2026-05-23-1.sqlite if present.
# Pass --file <path> to push something else.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

REC="${1:-$REPO_ROOT/.context/recordings/track-sonoma-2026-05-23-1.sqlite}"
if [ "$1" = "--file" ] && [ -n "${2:-}" ]; then
  REC="$2"
fi

hr
say "Step 40 — stage recording → phone bridge DB"
hr
SERIAL=$(detect_serial)

if [ ! -f "$REC" ]; then
  warn "Recording not found at: $REC"
  warn "Either record one with the bridge first, or pass a different path:"
  warn "  ./deploy/phone/40-stage-recording.sh /path/to/session.sqlite"
  exit 1
fi

SIZE=$(ls -lh "$REC" | awk '{print $5}')
say "Source:  $REC  ($SIZE)"
say "Archiving any existing on-phone DB first…"
termuxrun "$SERIAL" '
  mkdir -p ~/pitwall/data ~/pitwall/data/archive
  if [ -f ~/pitwall/data/pitwall_sessions.duckdb ]; then
    mv ~/pitwall/data/pitwall_sessions.duckdb \
       ~/pitwall/data/archive/pre-stage-$(date +%Y%m%dT%H%M%S).sqlite
    rm -f ~/pitwall/data/pitwall_sessions.duckdb.wal \
          ~/pitwall/data/pitwall_sessions.duckdb.shm
  fi
'

say "Pushing $SIZE …"
adb -s "$SERIAL" push "$REC" /data/local/tmp/pitwall-upload.sqlite | tail -1

termuxrun "$SERIAL" '
  cp /data/local/tmp/pitwall-upload.sqlite ~/pitwall/data/pitwall_sessions.duckdb
  python - <<EOF
import sqlite3
c = sqlite3.connect("/data/data/com.termux/files/home/pitwall/data/pitwall_sessions.duckdb")
sids = [r[0] for r in c.execute("SELECT session_id FROM sessions ORDER BY started_at DESC LIMIT 10")]
for tbl in ("sessions","telemetry","telemetry_signals","signal_registry"):
  n = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
  print(f"  {tbl:22s} {n}")
print("session_ids:", sids[:5])
EOF
'

hr
ok "Recording staged. Replay it later with:"
ok "  curl -X POST http://127.0.0.1:8765/session/replay/start \\"
ok "       -d '{\"source_session_id\":\"<id>\", \"speed\": 1, \"loop\": false}'"
