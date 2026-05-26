"""pitwall._env — internal env-var helpers.

Centralises the deprecation-fallback pattern used by the two LiteRT-adjacent
configuration families. Operators historically tripped on `PITWALL_LITERT_*`
(the ADK→OpenAI-shim URL) vs `PITWALL_LITERTLM_*` (the LiteRT-LM Kotlin
sidecar) differing by a single "LM". The rename:

    PITWALL_LITERT_URL       → PITWALL_ADK_OPENAI_URL
    PITWALL_LITERT_MODEL     → PITWALL_ADK_OPENAI_MODEL
    PITWALL_LITERT_API_KEY   → PITWALL_ADK_OPENAI_API_KEY
    PITWALL_LITERTLM_URL     → PITWALL_LITERT_SIDECAR_URL
    PITWALL_LITERTLM_MODEL   → PITWALL_LITERT_SIDECAR_MODEL

`get_env_with_legacy` reads the new name first, then falls back to the old
name with a one-time DeprecationWarning + log line per process. Existing
deployments keep working unchanged; new docs/scripts use the new names.
"""
from __future__ import annotations

import logging
import os
import threading
import warnings
from typing import Optional

_log = logging.getLogger(__name__)

_warned: set[str] = set()
_warned_lock = threading.Lock()


def get_env_with_legacy(
    new: str,
    old: str,
    default: Optional[str] = None,
) -> Optional[str]:
    """Read `new` env var; fall back to `old` (with deprecation warning); else default.

    Returns the string value, or ``default`` if neither name is set. The
    deprecation warning is emitted at most once per (old) name per process so
    long-running bridges don't spam logs on every read.
    """
    v = os.environ.get(new)
    if v is not None:
        return v

    v = os.environ.get(old)
    if v is not None:
        with _warned_lock:
            first_time = old not in _warned
            if first_time:
                _warned.add(old)
        if first_time:
            msg = f"{old} is deprecated; use {new} instead"
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            _log.warning(msg)
        return v

    return default
