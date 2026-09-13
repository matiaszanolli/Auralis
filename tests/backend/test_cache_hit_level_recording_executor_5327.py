"""Regression test: cache-hit level recording must use the streaming
executor, not the shared default I/O pool (#5327).

process_chunk_only()'s cache-HIT branch calls note_cached_chunk_level to
keep the LevelManager's history chronologically in sync (#3832). The
cache-MISS DSP call a few lines below it already runs on the dedicated
streaming pool installed by executors.py (#5086) — this call was missed
by that split and ran on a bare asyncio.to_thread() (the shared default
I/O pool) instead, so a library scan or other repository-heavy work
occupying that pool could delay cache-hit chunk delivery.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_cache import SimpleChunkCache
from core.stream_chunk_ops import process_chunk_only

pytestmark = pytest.mark.asyncio


def _make_controller_and_processor():
    cache = SimpleChunkCache()
    audio = np.zeros((100, 2), dtype=np.float32)
    cache.put(
        track_id=1,
        chunk_idx=0,
        preset="adaptive",
        intensity=1.0,
        audio=audio,
        sample_rate=44100,
        file_signature="sig",
        gain_db=-1.5,
        targets_hash="none",
    )

    controller = MagicMock()
    controller.cache_manager = cache

    processor = MagicMock()
    processor.track_id = 1
    processor.total_chunks = 1
    processor.preset = "adaptive"
    processor.intensity = 1.0
    processor.file_signature = "sig"
    processor.targets_hash = "none"
    processor.note_cached_chunk_level = MagicMock()

    return controller, processor


async def test_cache_hit_level_recording_uses_stream_executor():
    """The core assertion the issue's Test Plan asks for: note_level is
    routed through run_in_stream_executor, not a bare asyncio.to_thread()
    on the shared default pool.

    Patching run_in_stream_executor directly (rather than asyncio.to_thread)
    is deliberate: run_in_stream_executor itself falls back to
    asyncio.to_thread when no pool is installed (correct, documented
    behavior in executors.py) — in that fallback state the two are
    indistinguishable by watching to_thread alone, so asserting on the
    dedicated-executor entry point is the only way to prove the call site
    goes through the right abstraction regardless of whether a pool has
    been installed in this test's process.
    """
    controller, processor = _make_controller_and_processor()

    with patch(
        "core.executors.run_in_stream_executor", new_callable=AsyncMock
    ) as mock_stream_exec:
        await process_chunk_only(controller, 0, processor)

    mock_stream_exec.assert_awaited_once()
    called_func = mock_stream_exec.await_args.args[0]
    assert called_func is processor.note_cached_chunk_level
