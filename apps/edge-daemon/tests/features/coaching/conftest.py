"""
Shared coaching-test setup.

Per ADR-024 + ADR-025 the warm path is LocalLLM-only and the in-process
`litert_lm.Engine` path was retired. Coaching tests monkeypatch
`LitertCoach._generate_http` directly to simulate transport success /
failure — no env scaffolding needed.
"""
from __future__ import annotations

# Re-export helpers from the top-level conftest. Tests in this directory do
# `from conftest import _start_session, _frames_to_payload` and Python's
# conftest resolution would otherwise hide the parent module behind this one.
from tests.conftest import _start_session, _frames_to_payload  # noqa: E402, F401
