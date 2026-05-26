#!/usr/bin/env bash
# Step 30 — create the Python venv and install pitwall's runtime deps.
# - flask, flask-cors, waitress, numpy, pyyaml, python-can, cantools, pyserial
# - duckdb stub (no aarch64 wheel; backend falls back to SQLite from stdlib)
# Idempotent — re-running just reconciles the venv.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/_common.sh"

hr
say "Step 30 — Python venv + pip deps"
hr
SERIAL=$(detect_serial)

termuxrun "$SERIAL" '
  cd ~/pitwall
  if [ ! -d .venv ]; then
    python -m venv .venv
  fi
  . .venv/bin/activate
  pip install --upgrade pip 2>&1 | tail -2
  echo "--- installing runtime deps ---"
  pip install --prefer-binary \
    flask flask-cors waitress numpy pyyaml python-can cantools pyserial 2>&1 | tail -5
  echo
  echo "--- verifying imports ---"
  python -c "import flask, can, cantools, yaml, serial, numpy; print(\"ok — flask\",flask.__version__,\"can\",can.__version__,\"cantools\",cantools.__version__)"
'

say "Installing duckdb stub (Termux has no aarch64 wheel → bridge falls back to SQLite)…"
termuxrun "$SERIAL" '
  cd ~/pitwall
  . .venv/bin/activate
  SP=$(python -c "import sys; print([p for p in sys.path if \"site-packages\" in p][0])")
  mkdir -p "$SP/duckdb"
  cat > "$SP/duckdb/__init__.py" <<EOF
"""Stub duckdb so importing succeeds — the real backend used at runtime
is SQLite (pitwall.db detects this via probe-and-fallback)."""
class Error(Exception): pass
class DuckDBPyConnection: pass
class _Unavailable(RuntimeError): pass
def connect(*a, **kw):
    raise _Unavailable("duckdb not available on this platform")
__version__ = "0.0.0-stub"
EOF
  python -c "import sqlite3, sys; sys.path.insert(0,\"apps/bridge\"); from pitwall.db import db_backend; print(\"db backend:\", db_backend())"
'

hr
ok "Python deps installed. Next: ./deploy/phone/40-stage-recording.sh   (optional, for replay)"
ok "  or skip straight to: ./deploy/phone/60-forward-ports.sh + 70-start-bridge.sh"
