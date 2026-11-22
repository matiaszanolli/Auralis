"""
The frontend's mirrors of backend stream timing stay in step with the backend (#6634, #6555, #6640)

audioConstants.BACKEND_STREAM_TIMING hand-copies backend budgets and said "update the mirror in
the same commit", but nothing read both sides, so it drifted: #6336 added the 90 s
PROCESSOR_INIT_TIMEOUT and the stream-start watchdog kept firing at 45 s, cutting off a slow
processor build the backend was still within budget for (#6555). These tests parse the TypeScript
and compare it with the live Python constants.
"""

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "auralis-web" / "backend"
_FRONTEND = _ROOT / "auralis-web" / "frontend" / "src"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from config.limits import WS_HEARTBEAT_INTERVAL_SECONDS  # noqa: E402
from core import audio_stream_controller as asc  # noqa: E402
from core.chunk_boundaries import CHUNK_INTERVAL  # noqa: E402
from core.stream_protocol import FLOAT32_BYTES, PCM_FRAME_TARGET_BYTES  # noqa: E402


def _ts_number(relpath: str, name: str) -> float:
    """The numeric literal assigned to ``name`` (a const or an object key) in a frontend file."""
    source = (_FRONTEND / relpath).read_text()
    match = re.search(rf"\b{name}\s*[:=]\s*([\d_.]+(?:\s*\*\s*[\d_.]+)*)\s*[,;]", source)
    assert match, f"{name} not found as a numeric literal in {relpath}"
    value = 1.0
    for factor in match.group(1).split("*"):
        value *= float(factor.strip().replace("_", ""))
    return value


@pytest.mark.parametrize(
    ("ts_key", "backend_value"),
    [
        ("chunkIntervalSeconds", CHUNK_INTERVAL),
        ("streamSemaphoreWaitSeconds", asc.STREAM_ACQUIRE_TIMEOUT_SECONDS),
        ("processorInitTimeoutSeconds", asc.PROCESSOR_INIT_TIMEOUT),
    ],
)
def test_backend_stream_timing_mirror_matches_the_backend(ts_key, backend_value):
    assert _ts_number("services/audio/audioConstants.ts", ts_key) == backend_value


def test_stream_start_watchdog_outlasts_the_backends_own_bound():
    """#6555: the backend answers a slow processor build with audio_stream_error after the slot
    wait plus PROCESSOR_INIT_TIMEOUT; the client watchdog must not fire before that."""
    source = (_FRONTEND / "services/audio/audioConstants.ts").read_text()
    derivation = source.split("STREAM_START_WATCHDOG_DERIVED_MS =", 1)[1].split(";", 1)[0]
    terms = re.findall(r"BACKEND_STREAM_TIMING\.(\w+)", derivation)
    watchdog_s = sum(_ts_number("services/audio/audioConstants.ts", term) for term in terms)

    assert {"streamSemaphoreWaitSeconds", "processorInitTimeoutSeconds"} <= set(terms)
    assert watchdog_s > asc.STREAM_ACQUIRE_TIMEOUT_SECONDS + asc.PROCESSOR_INIT_TIMEOUT


def test_heartbeat_interval_mirrors_the_backend():
    assert _ts_number("config/timing.ts", "WS_HEARTBEAT_INTERVAL_MS") == WS_HEARTBEAT_INTERVAL_SECONDS * 1000


def test_pending_frame_cap_still_holds_several_chunks():
    """#6640: MAX_PENDING_CHUNK_FRAMES is sized in backend PCM frames ("several 10 s chunks");
    a smaller frame budget would quietly shrink it below one chunk."""
    frames = _ts_number("hooks/enhancement/audioChunkIngest.ts", "MAX_PENDING_CHUNK_FRAMES")
    chunk_bytes = CHUNK_INTERVAL * 48000 * 2 * FLOAT32_BYTES  # one interval of 48 kHz stereo

    assert frames * PCM_FRAME_TARGET_BYTES >= 3 * chunk_bytes
