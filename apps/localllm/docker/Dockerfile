# Trackside-laptop Gemma 4 (QLoRA-fine-tuned) container.
# Air-gapped fallback per PRD §6.4 — boots the LocalLLM server with
# the team's track-telemetry-tuned weights mounted from the host.

# TODO(team): pin to a specific base image + LocalLLM release tag.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Placeholder install — replace with the team's actual distribution
# channel (pip wheel, release binary, etc.).
RUN echo "TODO(team): install the LocalLLM server binary here"

# Config + weights are mounted by compose.yaml, not baked in.
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/v1/models || exit 1

CMD ["localllm", "serve", "--config", "/etc/localllm/trackside.toml", \
     "--host", "0.0.0.0", "--port", "8080"]
