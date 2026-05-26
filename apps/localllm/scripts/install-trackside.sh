#!/usr/bin/env bash
# Install LocalLLM on a trackside laptop via Docker. Used as the
# air-gapped fallback per PRD §6.4 when Vertex AI is unreachable.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$HERE/.." && pwd)"

cd "$APP_ROOT/docker"

if ! command -v docker >/dev/null 2>&1; then
    echo "fatal: docker not installed" >&2
    exit 1
fi

echo "building image…"
docker compose build

echo "starting…"
docker compose up -d

echo "waiting for /v1/models …"
for _ in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8080/v1/models >/dev/null; then
        echo "ok — http://127.0.0.1:8080/v1/models"
        exit 0
    fi
    sleep 1
done

echo "fatal: server did not respond within 30s" >&2
docker compose logs --tail=50
exit 2
