"""FastAPI entrypoint for the cloud backend.

Mounts the public API surface and a deliberately tiny `/health`
endpoint that the air-gapped paddock-sync framework polls before
attempting a cold-path generation. Vertex AI binding is deferred to
`cloud_backend.services` and lazy-loaded so the server boots without
GCP credentials in dev.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from pydantic import BaseModel

from . import __version__

logger = logging.getLogger("cloud_backend")

app = FastAPI(
    title="Trustable AI Super App — Cloud Backend",
    version=__version__,
    description="Strategic reasoning, DEL synthesis, cold-path curriculum.",
)


class Health(BaseModel):
    ok: bool
    version: str
    vertex_configured: bool


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(
        ok=True,
        version=__version__,
        vertex_configured=bool(os.environ.get("GOOGLE_CLOUD_PROJECT")),
    )


# Route modules mount themselves here as they land. Keep this section
# explicit — no auto-discovery — so the platform team can read the
# surface area at a glance.
# from cloud_backend.api import curriculum, debrief, gold_trace, paddock_sync
# app.include_router(curriculum.router)
# app.include_router(debrief.router)
# app.include_router(gold_trace.router)
# app.include_router(paddock_sync.router)


def run() -> None:
    """Console-script entrypoint (see pyproject.toml `[project.scripts]`)."""
    import uvicorn

    uvicorn.run(
        "cloud_backend.main:app",
        host=os.environ.get("CLOUD_BACKEND_HOST", "127.0.0.1"),
        port=int(os.environ.get("CLOUD_BACKEND_PORT", "8088")),
        log_level=os.environ.get("CLOUD_BACKEND_LOG", "info"),
        reload=bool(os.environ.get("CLOUD_BACKEND_RELOAD")),
    )


if __name__ == "__main__":  # pragma: no cover
    run()
