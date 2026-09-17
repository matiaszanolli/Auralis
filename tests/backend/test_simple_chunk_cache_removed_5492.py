"""
Regression tests: the in-memory SimpleChunkCache is gone (#5492)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

process_chunk_only() consulted core/chunk_cache.py::SimpleChunkCache only
when controller.cache_manager was that class, which in the healthy app it
never was (it is the StreamlinedCacheManager singleton). The in-memory tier
therefore ran only in degraded mode. It was deleted; every chunk request now
goes through ChunkedAudioProcessor.process_chunk_safe(), whose on-disk tier
serves hits and restores level history in both modes.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import audio_stream_controller
from core.stream_chunk_ops import process_chunk_only


def test_module_and_fallback_are_deleted():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("core.chunk_cache")
    assert not hasattr(audio_stream_controller, "get_fallback_chunk_cache")
    assert not hasattr(audio_stream_controller, "SimpleChunkCache")


@pytest.mark.asyncio
@pytest.mark.parametrize("cache_manager", [None, MagicMock()], ids=["degraded", "healthy"])
async def test_every_chunk_goes_through_the_processor(cache_manager):
    """Healthy and degraded mode take the same path: the processor's own
    (disk-cached) process_chunk_safe()."""
    controller = audio_stream_controller.AudioStreamController(cache_manager=cache_manager)
    pcm = np.zeros((16, 2), dtype=np.float32)
    processor = MagicMock(sample_rate=44100, total_chunks=1)
    processor.process_chunk_safe = AsyncMock(return_value=(Path("/tmp/c.wav"), pcm))

    samples, sr = await process_chunk_only(controller, 0, processor)

    processor.process_chunk_safe.assert_awaited_once_with(0, fast_start=True)
    assert samples is pcm
    assert sr == 44100
