#!/usr/bin/env bash
# Smoke probe for any LocalLLM deploy mode (phone or trackside).
# Called from deploy/phone/00-check.sh and from cloud-backend's
# air-gapped-fallback decision logic.
set -euo pipefail

URL="${LOCALLLM_URL:-http://127.0.0.1:8080}"

code=$(curl -s -o /tmp/localllm-health.json -w '%{http_code}' \
        "$URL/v1/models" 2>/dev/null || echo "000")

if [ "$code" = "200" ]; then
    echo "ok — $URL/v1/models → 200"
    cat /tmp/localllm-health.json
    exit 0
fi

echo "fail — $URL/v1/models → $code"
exit 1
