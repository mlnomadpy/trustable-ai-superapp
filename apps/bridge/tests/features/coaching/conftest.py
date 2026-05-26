"""
Shared coaching-test setup.

Per ADR-022 the production default for both `LitertCoach` (warm path,
brief/debrief) and the ADK paddock backend is HTTP-to-LocalLLM. Most
existing coaching tests, however, validate the **in-process** behaviour
(engine load / failure / mock conversation). To keep them deterministic
without a LocalLLM instance running, this conftest opts them out of
HTTP mode at import time by clearing `PITWALL_ADK_OPENAI_URL` (legacy
alias `PITWALL_LITERT_URL`) and forcing the ADK backend back to its
legacy `litertlm` selector.

Setting these via `os.environ` here — rather than via a function-scoped
`monkeypatch` fixture — matters because module- and session-scoped
fixtures (e.g. the `litert_coach` integration fixture) construct their
coach *before* function-scoped fixtures run, and the env must already
be applied at that point.

Tests that want to validate the HTTP path should
`monkeypatch.setenv("PITWALL_ADK_OPENAI_URL", ...)` themselves
(the legacy `PITWALL_LITERT_URL` is still honoured with a
DeprecationWarning).
"""
from __future__ import annotations

import os

# Clear both the current and legacy names so a stray env from the
# operator's shell doesn't leak into the in-process test paths.
os.environ["PITWALL_ADK_OPENAI_URL"] = ""
os.environ["PITWALL_LITERT_URL"] = ""
os.environ["PITWALL_ADK_BACKEND"] = "litertlm"

# Re-export helpers from the top-level conftest. Tests in this directory do
# `from conftest import _start_session, _frames_to_payload` and Python's
# conftest resolution would otherwise hide the parent module behind this one.
from tests.conftest import _start_session, _frames_to_payload  # noqa: E402, F401
