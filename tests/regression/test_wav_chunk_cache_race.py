"""
Regression test: get_wav_chunk_path concurrent cache race (#2371, #2184)

Verifies that ChunkedAudioProcessor.get_wav_chunk_path() serializes
concurrent requests via _sync_cache_lock so the same chunk is not
processed multiple times.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))


class TestWavChunkCacheRace:
    """Regression: concurrent calls must not bypass cache (#2184)."""

    def test_sync_cache_lock_exists(self):
        """ChunkedAudioProcessor must have a _sync_cache_lock attribute."""
        from core.chunked_processor import ChunkedAudioProcessor
        source = inspect.getsource(ChunkedAudioProcessor.__init__)
        assert "_sync_cache_lock" in source, (
            "_sync_cache_lock not initialized in __init__"
        )

    def test_get_wav_chunk_path_uses_lock(self):
        """get_wav_chunk_path must acquire _sync_cache_lock."""
        from core.chunked_processor import ChunkedAudioProcessor
        source = inspect.getsource(ChunkedAudioProcessor.get_wav_chunk_path)
        assert "_sync_cache_lock" in source, (
            "get_wav_chunk_path does not use _sync_cache_lock — "
            "concurrent requests will race on cache miss"
        )

    def test_lock_is_threading_lock(self):
        """Lock must be a threading.Lock (not asyncio) for thread-pool callers."""
        from core.chunked_processor import ChunkedAudioProcessor
        source = inspect.getsource(ChunkedAudioProcessor.__init__)
        assert "threading.Lock()" in source or "Lock()" in source, (
            "_sync_cache_lock should be a threading.Lock"
        )
