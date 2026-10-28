"""The chunk-cancel registry lives in core.stream_gates, not behind a router import (#5974).

stream_enhanced / stream_seek did a call-time `from routers.system import
_stream_chunk_cancel_events`, coupling the audio path to the router layer while the pause and
flow registries had already moved next to the pumps.
"""

import re
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from core import stream_gates  # noqa: E402
from ws_handlers.context import StreamState  # noqa: E402


def test_no_core_module_imports_the_router_layer_for_stream_state():
    offenders = [
        path.name
        for path in sorted((_BACKEND / "core").glob("stream_*.py"))
        if re.search(r"^\s*from routers[\w.]* import", path.read_text(), re.MULTILINE)
    ]

    assert offenders == []


def test_the_router_wires_the_core_registry_into_stream_state():
    import routers.system as system

    source = Path(system.__file__).read_text()

    assert "chunk_cancel_events=stream_chunk_cancel_events" in source
    assert isinstance(stream_gates.stream_chunk_cancel_events, dict)
    assert "chunk_cancel_events" in StreamState.__dataclass_fields__
