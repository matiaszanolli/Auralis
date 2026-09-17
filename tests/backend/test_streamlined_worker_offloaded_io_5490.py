"""
Regression tests: the streamlined cache worker keeps file I/O off the loop (#5490)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

FileSignatureService.generate() opens, reads and SHA-256-hashes the source
file. ensure_tier1_chunk() and StreamlinedCacheWorker._process_chunk() called
it directly on the event loop on every ~1 s worker tick, stalling WebSocket
traffic whenever the library sits on slow storage. Both calls, and
_process_chunk's existence check, must run in a worker thread.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import streamlined_tiers
from core.file_signature import FileSignatureService
from core.streamlined_worker import StreamlinedCacheWorker


def _recording_generate(threads: list[threading.Thread]):
    def generate(_filepath: str) -> str:
        threads.append(threading.current_thread())
        return "sig"
    return generate


@pytest.mark.asyncio
async def test_ensure_tier1_chunk_hashes_off_the_loop():
    threads: list[threading.Thread] = []
    worker = Mock()
    worker.cache_manager.get_chunk = AsyncMock(return_value=(None, None))
    worker.cache_manager.auto_mastering_enabled = False
    worker.cache_manager.warm_tier1_immediately = AsyncMock()
    worker._process_chunk = AsyncMock(return_value=None)

    with patch.object(FileSignatureService, "generate", side_effect=_recording_generate(threads)):
        await streamlined_tiers.ensure_tier1_chunk(
            worker, Mock(filepath="/tmp/t.wav"), 1, 0, "adaptive", 1.0
        )

    assert threads, "generate() was not called"
    assert all(t is not threading.current_thread() for t in threads)
    # The signature still reaches the lookup.
    assert worker.cache_manager.get_chunk.await_args.kwargs["file_signature"] == "sig"


@pytest.mark.asyncio
async def test_process_chunk_stats_and_hashes_off_the_loop():
    loop_thread = threading.current_thread()
    sig_threads: list[threading.Thread] = []
    exists_threads: list[threading.Thread] = []

    def exists() -> bool:
        exists_threads.append(threading.current_thread())
        return True

    worker = StreamlinedCacheWorker(Mock(), Mock())
    build = AsyncMock(side_effect=RuntimeError("stop after the key is built"))

    with patch("core.streamlined_worker.Path") as mock_path, \
         patch.object(FileSignatureService, "generate", side_effect=_recording_generate(sig_threads)), \
         patch("core.streamlined_worker.get_or_build_processor", build):
        mock_path.return_value.exists = exists
        result = await worker._process_chunk(
            Mock(filepath="/tmp/t.wav"), 1, 0, "adaptive", 1.0, "tier1"
        )

    assert result is None
    assert exists_threads and exists_threads[0] is not loop_thread
    assert sig_threads and sig_threads[0] is not loop_thread
    assert build.await_args.args[1][3] == "sig"
