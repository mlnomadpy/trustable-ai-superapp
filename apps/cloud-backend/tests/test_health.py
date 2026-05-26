"""Smoke test — boots the FastAPI app without any GCP credentials."""

from __future__ import annotations

from fastapi.testclient import TestClient

from cloud_backend.main import app


def test_health_responds_ok() -> None:
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert "version" in body
        assert body["vertex_configured"] is False  # no GOOGLE_CLOUD_PROJECT in CI
