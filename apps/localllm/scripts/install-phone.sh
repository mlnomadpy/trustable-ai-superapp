#!/data/data/com.termux/files/usr/bin/bash
# Install LocalLLM on Termux/Pixel-10. Idempotent — re-running is a no-op
# beyond reconciling the runit service.
#
# Prerequisites: Termux + termux-services (`pkg install termux-services`).
#
# Steps:
#   1. Download Gemma 4 E2B int8 weights into ~/llms/gemma-4-e2b-q8/
#      (if missing — skipped when the dir already has the .bin).
#   2. Install the LocalLLM binary (replace the placeholder pkg fetch
#      below with the team's actual distribution channel).
#   3. Symlink apps/localllm/service/localllm into $PREFIX/var/service/.
#   4. sv up localllm.

set -euo pipefail

REPO_ROOT="${HOME}/pitwall"   # whatever 20-stage-repo.sh extracted to
SERVICE_SRC="${REPO_ROOT}/apps/localllm/service/localllm"
SERVICE_DST="${PREFIX}/var/service/localllm"
WEIGHTS_DIR="${HOME}/llms/gemma-4-e2b-q8"

if [ ! -d "$REPO_ROOT/apps/localllm" ]; then
    echo "fatal: $REPO_ROOT/apps/localllm not found. Run deploy/phone/20-stage-repo.sh first." >&2
    exit 1
fi

# ── 1. Weights ──────────────────────────────────────────────────────
mkdir -p "$WEIGHTS_DIR"
if [ -z "$(ls -A "$WEIGHTS_DIR" 2>/dev/null || true)" ]; then
    echo "TODO(team): replace this with the actual weights fetch."
    echo "Expected at $WEIGHTS_DIR — abort until weights are present."
    exit 2
else
    echo "weights present at $WEIGHTS_DIR — skipping download"
fi

# ── 2. Binary ───────────────────────────────────────────────────────
if ! command -v localllm >/dev/null 2>&1; then
    echo "TODO(team): install the LocalLLM binary via team-internal channel"
    echo "(pkg install localllm  /  pip install localllm-server  /  release artifact)"
    exit 3
fi
echo "localllm binary: $(command -v localllm) ($(localllm --version 2>/dev/null || echo unknown))"

# ── 3. Service ──────────────────────────────────────────────────────
if [ ! -L "$SERVICE_DST" ]; then
    ln -s "$SERVICE_SRC" "$SERVICE_DST"
    echo "linked $SERVICE_SRC → $SERVICE_DST"
fi
chmod +x "$SERVICE_SRC/run" "$SERVICE_SRC/log/run"

# ── 4. Bring up ─────────────────────────────────────────────────────
sv-enable localllm 2>/dev/null || true
sv up localllm
sleep 1
sv status localllm

echo "ok — LocalLLM service brought up. Verify:"
echo "    curl http://127.0.0.1:8080/v1/models"
