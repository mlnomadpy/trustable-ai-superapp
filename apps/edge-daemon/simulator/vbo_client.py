"""
Backward-compatibility shim.

The simulator clients used to ship their own .vbo parser
(`ClientTelemetryFrame` + `parse_vbo_client`) under the rationale that
the simulator shouldn't import from the backend `pitwall.features`
namespace. That was inertia — the simulator ships as part of this
same repo, and `can_simulator.py` already imports backend modules at
runtime. There's now exactly one .vbo parser in the tree
(`pitwall.features.session.vbo_parser.parse_vbo`), and the simulator
clients delegate to it via `vbo_replay`.

New code should `from vbo_replay import load_frames, TelemetryFrame`
(or import from `pitwall.features.session.vbo_parser` directly). This
module is kept only so external scripts that still write `from
vbo_client import parse_vbo_client` keep working; it will be removed
in a future cleanup.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make sibling-module import work whether this file is loaded as
# `simulator.vbo_client` (namespace-package style, when launched via
# `python -m simulator.simulator`) or as plain `vbo_client` (when
# launched via `python simulator.py` from inside src/simulator/).
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from vbo_replay import (  # type: ignore[import-not-found]  # noqa: E402, F401
    TelemetryFrame,
    frame_to_payload,
    load_frames,
)

# Legacy alias — old code wrote `ClientTelemetryFrame`; both names
# now resolve to the production TelemetryFrame dataclass.
ClientTelemetryFrame = TelemetryFrame


def parse_vbo_client(filepath):
    """Deprecated alias for `vbo_replay.load_frames`."""
    return load_frames(filepath)
