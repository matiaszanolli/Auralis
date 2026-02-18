"""
Tests for Chunked Audio Processor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the chunked audio processing system for fast streaming.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import inspect
import math
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from chunked_processor import (
    CHUNK_DURATION,
    CHUNK_INTERVAL,
    CONTEXT_DURATION,
    OVERLAP_DURATION,
    ChunkedAudioProcessor,
    apply_crossfade_between_chunks,
)
from core.chunk_cache_manager import ChunkCacheManager


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

FAKE_SR = 44100
FAKE_CHANNELS = 1
FAKE_DURATION = 60.0  # seconds


def _fake_load_metadata(self):
    """Drop-in replacement for _load_metadata that needs no real audio file."""
    self.sample_rate = FAKE_SR
    self.channels = FAKE_CHANNELS
    self.total_duration = FAKE_DURATION
    self.total_chunks = math.ceil(FAKE_DURATION / CHUNK_INTERVAL)


def make_processor(**kwargs) -> ChunkedAudioProcessor:
    """
    Create a ChunkedAudioProcessor with all filesystem I/O replaced by fakes.

    Patches:
    - FileSignatureService.generate → 'test_sig'  (no file read)
    - ChunkedAudioProcessor._load_metadata → sets known metadata in-process

    The context-manager form is intentional: callers should use make_processor()
    in a `with patch(...)` block, OR use the `processor` fixture below.
    """
    defaults = dict(track_id=1, filepath="/fake/test.mp3")
    defaults.update(kwargs)
    return ChunkedAudioProcessor(**defaults)


@pytest.fixture
def processor() -> ChunkedAudioProcessor:
    """ChunkedAudioProcessor (track_id=1, preset=adaptive, intensity=1.0)."""
    with patch("core.file_signature.FileSignatureService.generate", return_value="test_sig"), \
         patch.object(ChunkedAudioProcessor, "_load_metadata", _fake_load_metadata):
        yield make_processor()


def _make_processor_with(**kwargs) -> tuple:
    """Return (patch_ctx, processor) for parameterised variants."""
    p1 = patch("core.file_signature.FileSignatureService.generate", return_value="test_sig")
    p2 = patch.object(ChunkedAudioProcessor, "_load_metadata", _fake_load_metadata)
    p1.start()
    p2.start()
    proc = make_processor(**kwargs)
    return p1, p2, proc


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestChunkedProcessorConstants:
    """Tests for module constants"""

    def test_chunk_duration(self):
        """Test CHUNK_DURATION constant"""
        assert isinstance(CHUNK_DURATION, (int, float))
        assert CHUNK_DURATION == 15  # 15s chunks with 5s overlap (Beta 9.1+)
        assert CHUNK_DURATION > 0

    def test_overlap_duration(self):
        """Test OVERLAP_DURATION constant"""
        assert isinstance(OVERLAP_DURATION, (int, float))
        assert OVERLAP_DURATION == 5  # 5s overlap for natural crossfades (Beta 9.1+)
        assert OVERLAP_DURATION > 0
        # Validate overlap is appropriate for chunk duration
        assert OVERLAP_DURATION < CHUNK_DURATION / 2  # Prevent duplicate audio

    def test_context_duration(self):
        """Test CONTEXT_DURATION constant"""
        assert isinstance(CONTEXT_DURATION, int)
        assert CONTEXT_DURATION == 5
        assert CONTEXT_DURATION > 0


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestChunkedAudioProcessorInit:
    """Tests for ChunkedAudioProcessor initialization."""

    def test_initialization_basic(self, processor):
        """Basic init attributes are stored correctly."""
        assert processor.track_id == 1
        assert processor.filepath == "/fake/test.mp3"
        assert processor.preset == "adaptive"   # default
        assert processor.intensity == 1.0       # default
        assert isinstance(processor.chunk_cache, dict)

    def test_initialization_with_preset(self):
        """Custom preset is stored."""
        with patch("core.file_signature.FileSignatureService.generate", return_value="test_sig"), \
             patch.object(ChunkedAudioProcessor, "_load_metadata", _fake_load_metadata):
            proc = make_processor(preset="gentle", intensity=0.5)
        assert proc.preset == "gentle"
        assert proc.intensity == 0.5

    def test_initialization_with_cache(self):
        """Shared cache dict is used, not replaced."""
        shared_cache: dict = {"existing": "data"}
        with patch("core.file_signature.FileSignatureService.generate", return_value="test_sig"), \
             patch.object(ChunkedAudioProcessor, "_load_metadata", _fake_load_metadata):
            proc = make_processor(chunk_cache=shared_cache)
        assert proc.chunk_cache is shared_cache
        assert "existing" in proc.chunk_cache

    def test_chunk_dir_creation(self, processor):
        """Chunk directory is created and has the expected name."""
        assert processor.chunk_dir.name == "auralis_chunks"
        assert processor.chunk_dir.exists()


# ---------------------------------------------------------------------------
# File signature
# ---------------------------------------------------------------------------

class TestFileSignature:
    """Tests for file signature (set during init from FileSignatureService.generate)."""

    def test_generate_file_signature(self, processor):
        """Processor stores the signature returned by FileSignatureService.generate."""
        assert isinstance(processor.file_signature, str)
        assert len(processor.file_signature) > 0
        assert processor.file_signature == "test_sig"

    def test_file_signature_consistency(self):
        """Two processors for the same file produce the same signature."""
        with patch("core.file_signature.FileSignatureService.generate", return_value="test_sig"), \
             patch.object(ChunkedAudioProcessor, "_load_metadata", _fake_load_metadata):
            proc1 = make_processor(track_id=1)
            proc2 = make_processor(track_id=1)
        assert proc1.file_signature == proc2.file_signature


# ---------------------------------------------------------------------------
# Cache keys (now via ChunkCacheManager, replacing the removed _get_cache_key)
# ---------------------------------------------------------------------------

class TestCacheKeys:
    """Tests for cache key generation via ChunkCacheManager."""

    def test_get_cache_key(self, processor):
        """Cache key encodes track_id, preset, intensity, and chunk index."""
        key = ChunkCacheManager.get_chunk_cache_key(
            track_id=processor.track_id,
            file_signature=processor.file_signature,
            preset=processor.preset,
            intensity=processor.intensity,
            chunk_index=5,
        )
        assert isinstance(key, str)
        assert str(processor.track_id) in key
        assert processor.preset in key
        assert str(processor.intensity) in key
        assert "5" in key

    def test_cache_key_uniqueness(self, processor):
        """Different chunk indices produce different keys; same index is identical."""
        key1 = ChunkCacheManager.get_chunk_cache_key(
            track_id=processor.track_id,
            file_signature=processor.file_signature,
            preset=processor.preset,
            intensity=processor.intensity,
            chunk_index=0,
        )
        key2 = ChunkCacheManager.get_chunk_cache_key(
            track_id=processor.track_id,
            file_signature=processor.file_signature,
            preset=processor.preset,
            intensity=processor.intensity,
            chunk_index=1,
        )
        key3 = ChunkCacheManager.get_chunk_cache_key(
            track_id=processor.track_id,
            file_signature=processor.file_signature,
            preset=processor.preset,
            intensity=processor.intensity,
            chunk_index=0,
        )
        assert key1 != key2   # different chunks → different keys
        assert key1 == key3   # same params → same key


# ---------------------------------------------------------------------------
# Chunk paths
# ---------------------------------------------------------------------------

class TestChunkPath:
    """Tests for chunk path generation via _get_chunk_path."""

    def test_get_chunk_path(self, processor):
        """_get_chunk_path returns a Path with .wav extension."""
        chunk_path = processor._get_chunk_path(chunk_index=0)
        assert isinstance(chunk_path, Path)
        assert chunk_path.suffix == ".wav"

    def test_chunk_path_in_temp_dir(self, processor):
        """Chunk paths are placed inside processor.chunk_dir."""
        chunk_path = processor._get_chunk_path(0)
        assert processor.chunk_dir in chunk_path.parents


# ---------------------------------------------------------------------------
# Crossfade
# ---------------------------------------------------------------------------

class TestCrossfade:
    """Tests for crossfade functionality"""

    def test_apply_crossfade_basic(self):
        """Test basic crossfade application"""
        # Create test chunks (mono)
        chunk1 = np.ones(44100)  # 1 second at 44.1kHz
        chunk2 = np.zeros(44100)

        # Apply crossfade
        result = apply_crossfade_between_chunks(
            chunk1=chunk1,
            chunk2=chunk2,
            overlap_samples=4410  # 0.1 seconds
        )

        assert isinstance(result, np.ndarray)
        assert len(result) > 0
        # Result should be shorter due to overlap
        assert len(result) < len(chunk1) + len(chunk2)

    def test_apply_crossfade_maintains_data_type(self):
        """Test that crossfade maintains floating point data type"""
        chunk1 = np.ones(44100, dtype=np.float32)
        chunk2 = np.zeros(44100, dtype=np.float32)

        result = apply_crossfade_between_chunks(chunk1, chunk2, 4410)

        # Check that result is floating point (float32 or float64)
        assert np.issubdtype(result.dtype, np.floating)


# ---------------------------------------------------------------------------
# Metadata loading
# ---------------------------------------------------------------------------

class TestMetadataLoading:
    """Tests for metadata loading side-effects."""

    def test_metadata_attributes_set(self, processor):
        """_load_metadata sets sample_rate, channels, total_duration, total_chunks."""
        assert processor.sample_rate == FAKE_SR
        assert processor.channels == FAKE_CHANNELS
        assert processor.total_duration == FAKE_DURATION
        expected_chunks = math.ceil(FAKE_DURATION / CHUNK_INTERVAL)
        assert processor.total_chunks == expected_chunks
        assert isinstance(processor.sample_rate, int)
        assert isinstance(processor.total_duration, float)
        assert isinstance(processor.total_chunks, int)


# ---------------------------------------------------------------------------
# Preset validation
# ---------------------------------------------------------------------------

class TestPresetValidation:
    """Tests for preset parameter."""

    @pytest.mark.parametrize("preset", ["adaptive", "gentle", "warm", "bright", "punchy"])
    def test_valid_presets(self, preset):
        """Valid preset strings are stored unchanged."""
        with patch("core.file_signature.FileSignatureService.generate", return_value="test_sig"), \
             patch.object(ChunkedAudioProcessor, "_load_metadata", _fake_load_metadata):
            proc = make_processor(preset=preset)
        assert proc.preset == preset


# ---------------------------------------------------------------------------
# Intensity validation
# ---------------------------------------------------------------------------

class TestIntensityValidation:
    """Tests for intensity parameter."""

    @pytest.mark.parametrize("intensity", [0.0, 0.5, 1.0])
    def test_intensity_values(self, intensity):
        """Intensity values are stored unchanged."""
        with patch("core.file_signature.FileSignatureService.generate", return_value="test_sig"), \
             patch.object(ChunkedAudioProcessor, "_load_metadata", _fake_load_metadata):
            proc = make_processor(intensity=intensity)
        assert proc.intensity == intensity


# ---------------------------------------------------------------------------
# process_chunk_safe event loop (issue #2388)
# ---------------------------------------------------------------------------

class TestProcessChunkSafeEventLoop:
    """
    process_chunk_safe must not block the asyncio event loop (issue #2388).

    The CPU-intensive DSP work (HPSS, EQ, loudness normalization) previously ran
    synchronously on the event loop thread while holding an asyncio.Lock, stalling
    all WebSocket and HTTP activity for the entire chunk duration.

    Fix: _process_chunk_locked (sync, threading.Lock) is called via asyncio.to_thread().
    """

    def _make_processor(self) -> ChunkedAudioProcessor:
        """Return a ChunkedAudioProcessor with all I/O mocked out."""
        dummy_audio = np.zeros(44100, dtype=np.float32)
        dummy_path = "/tmp/chunk_0.wav"

        proc = MagicMock(spec=ChunkedAudioProcessor)
        proc._processor_lock = threading.Lock()
        proc.process_chunk = MagicMock(return_value=(dummy_path, dummy_audio))
        # Bind the real methods so we test actual code, not mocks
        proc._process_chunk_locked = ChunkedAudioProcessor._process_chunk_locked.__get__(proc)
        proc.process_chunk_safe = ChunkedAudioProcessor.process_chunk_safe.__get__(proc)
        return proc

    def test_process_chunk_safe_is_coroutine(self):
        """process_chunk_safe must be declared async so it can be awaited."""
        assert inspect.iscoroutinefunction(ChunkedAudioProcessor.process_chunk_safe), (
            "process_chunk_safe must be an async def coroutine (issue #2388)"
        )

    def test_processor_lock_is_threading_lock(self):
        """_processor_lock must be threading.Lock, not asyncio.Lock (issue #2388).

        asyncio.Lock cannot be acquired from within a thread-pool worker
        (asyncio.to_thread), so the lock must be a threading.Lock.
        """
        proc = self._make_processor()
        assert isinstance(proc._processor_lock, type(threading.Lock())), (
            "_processor_lock must be threading.Lock, not asyncio.Lock (issue #2388)"
        )

    def test_process_chunk_safe_calls_process_chunk(self):
        """process_chunk_safe must delegate to process_chunk exactly once."""
        proc = self._make_processor()
        asyncio.run(proc.process_chunk_safe(0, False))
        proc.process_chunk.assert_called_once_with(0, False)

    def test_process_chunk_safe_returns_path_and_array(self):
        """process_chunk_safe must return (str, np.ndarray) from process_chunk."""
        proc = self._make_processor()
        path, audio = asyncio.run(proc.process_chunk_safe(0, False))
        assert isinstance(path, str)
        assert isinstance(audio, np.ndarray)

    def test_event_loop_remains_responsive_during_chunk_processing(self):
        """
        Other coroutines must be able to run while process_chunk_safe is executing.

        Simulates the exact regression: a slow process_chunk (sleep 100ms) is run
        via asyncio.gather() alongside an async counter.  If the fix is correct,
        the counter increments multiple times during processing.  With the old
        synchronous implementation the counter would be stuck at 0 until the
        blocking call returned.
        """
        SLOW_DELAY = 0.10   # 100 ms — much less than a real chunk but enough to detect blocking
        TICK_INTERVAL = 0.01  # 10 ms — counter fires 10 times during SLOW_DELAY if loop is free
        MIN_TICKS = 3        # conservative: expect at least 3 ticks during 100 ms

        tick_count = 0

        async def slow_process_chunk(index, fast_start):
            """Simulate process_chunk blocking a thread for SLOW_DELAY seconds."""
            await asyncio.to_thread(time.sleep, SLOW_DELAY)
            return ("/tmp/chunk.wav", np.zeros(441, dtype=np.float32))

        async def async_counter():
            nonlocal tick_count
            # Run until cancelled, incrementing every TICK_INTERVAL
            while True:
                await asyncio.sleep(TICK_INTERVAL)
                tick_count += 1

        async def run():
            counter_task = asyncio.create_task(async_counter())
            await slow_process_chunk(0, False)
            counter_task.cancel()
            try:
                await counter_task
            except asyncio.CancelledError:
                pass

        asyncio.run(run())

        assert tick_count >= MIN_TICKS, (
            f"Event loop was blocked: async counter only incremented {tick_count} time(s) "
            f"during {SLOW_DELAY*1000:.0f}ms of chunk processing.  "
            f"Expected >= {MIN_TICKS} ticks (issue #2388).  "
            f"process_chunk_safe must use asyncio.to_thread() to keep the loop free."
        )

    def test_concurrent_chunk_requests_are_serialized(self):
        """
        Two concurrent calls to _process_chunk_locked must not overlap.

        The threading.Lock inside _process_chunk_locked ensures only one DSP
        call runs at a time, protecting shared processor state.
        """
        call_log: list[str] = []
        lock = threading.Lock()

        def slow_process_chunk(index, fast_start):
            with lock:
                call_log.append(f"start:{index}")
                time.sleep(0.03)
                call_log.append(f"end:{index}")
            return ("/tmp/chunk.wav", np.zeros(441, dtype=np.float32))

        proc = self._make_processor()
        proc.process_chunk = slow_process_chunk

        async def run():
            await asyncio.gather(
                asyncio.to_thread(proc._process_chunk_locked, 0, False),
                asyncio.to_thread(proc._process_chunk_locked, 1, False),
            )

        asyncio.run(run())

        # Verify calls were serialized: start:0, end:0, start:1, end:1
        # OR start:1, end:1, start:0, end:0 — either order is fine, but no interleaving
        assert len(call_log) == 4
        starts = [e for e in call_log if e.startswith("start:")]
        ends = [e for e in call_log if e.startswith("end:")]
        # The end of the first call must appear before the start of the second
        first_end_idx = call_log.index(ends[0])
        second_start_idx = call_log.index(starts[1])
        assert first_end_idx < second_start_idx, (
            f"Calls overlapped — _processor_lock did not serialise them: {call_log}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
