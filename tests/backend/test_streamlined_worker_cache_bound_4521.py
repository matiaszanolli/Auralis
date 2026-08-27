"""
Tests for StreamlinedCacheWorker processor-cache bounding (issue #4521)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_processor_cache` grew one ChunkedAudioProcessor per distinct
(track_id, preset, intensity) with no cap. The only eviction lived in
`_build_tier2_cache`, which `_process_priorities` stops calling once
`is_track_fully_cached()` returns True — so a fully-cached track never reached
it and the cache grew for the life of the backend process.
`trigger_immediate_processing` never reached it at all.

These tests pin the bound at the *insertion* site so both routes are covered.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.streamlined_worker import (  # noqa: E402
    _PROCESSOR_CACHE_MAX,
    StreamlinedCacheWorker,
    _intensity_key,
)


@pytest.fixture
def mock_cache_manager():
    cm = Mock()
    cm.current_track_id = 1
    cm.auto_mastering_enabled = True
    # The regression: a fully-cached track never reaches _build_tier2_cache,
    # which is where the ONLY eviction used to live.
    cm.is_track_fully_cached = Mock(return_value=True)
    cm.add_chunk = AsyncMock(return_value=True)
    cm.warm_tier1_immediately = AsyncMock()
    cm.get_chunk = AsyncMock(return_value=(None, None))
    cm.get_track_cache_status = Mock(return_value=Mock(total_chunks=100))
    return cm


@pytest.fixture
def mock_library_database():
    lm = Mock()
    track = Mock()
    track.filepath = "/tmp/test_track.wav"
    lm.tracks.get_by_id = Mock(return_value=track)
    return lm


@pytest.fixture
def worker(mock_cache_manager, mock_library_database):
    return StreamlinedCacheWorker(mock_cache_manager, mock_library_database)


class _StubProcessor:
    """Stand-in for ChunkedAudioProcessor; records construction kwargs."""

    instances: list["_StubProcessor"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.intensity = kwargs.get("intensity")
        # Real ChunkedAudioProcessor.__init__ always sets this (#5251) —
        # _process_chunk() now reads it to pass through to add_chunk().
        self.file_signature = "stubsig"
        self.process_chunk_safe = AsyncMock(return_value=("/tmp/chunk.wav", None))
        _StubProcessor.instances.append(self)


@pytest.fixture
def stub_processor():
    _StubProcessor.instances = []
    with patch("core.streamlined_worker.Path") as mock_path, patch(
        "core.chunked_processor.ChunkedAudioProcessor", _StubProcessor
    ):
        mock_path.return_value.exists.return_value = True
        yield _StubProcessor


class TestProcessorCacheBound:
    """The cache must never exceed its documented cap."""

    @pytest.mark.asyncio
    async def test_distinct_tracks_bounded(self, worker, stub_processor):
        """MAX + 5 distinct track ids leave exactly MAX entries."""
        for track_id in range(_PROCESSOR_CACHE_MAX + 5):
            await worker._process_chunk(
                worker.library_database.tracks.get_by_id(track_id),
                track_id,
                0,
                preset="balanced",
                intensity=0.5,
                tier="tier1",
            )

        assert len(worker._processor_cache) == _PROCESSOR_CACHE_MAX
        assert len(stub_processor.instances) == _PROCESSOR_CACHE_MAX + 5

    @pytest.mark.asyncio
    async def test_eviction_is_lru_not_fifo(self, worker, stub_processor):
        """A re-touched key survives eviction; the untouched one goes."""
        for track_id in range(_PROCESSOR_CACHE_MAX):
            await worker._process_chunk(
                Mock(filepath="/tmp/t.wav"), track_id, 0, "balanced", 0.5, "tier1"
            )

        # Touch the oldest key (track 0) so it becomes most-recently-used.
        await worker._process_chunk(
            Mock(filepath="/tmp/t.wav"), 0, 1, "balanced", 0.5, "tier1"
        )
        # Now insert one more; the victim must be track 1, not track 0.
        await worker._process_chunk(
            Mock(filepath="/tmp/t.wav"), 999, 0, "balanced", 0.5, "tier1"
        )

        keys = {k[0] for k in worker._processor_cache}
        assert 0 in keys, "recently-used entry was evicted (FIFO, not LRU)"
        assert 1 not in keys
        assert len(worker._processor_cache) == _PROCESSOR_CACHE_MAX

    @pytest.mark.asyncio
    async def test_trigger_immediate_processing_is_bounded(
        self, worker, stub_processor
    ):
        """The seek path never touched _build_tier2_cache — it must still bound."""
        for track_id in range(_PROCESSOR_CACHE_MAX + 5):
            worker.library_database.tracks.get_by_id.return_value = Mock(
                filepath="/tmp/t.wav"
            )
            ok = await worker.trigger_immediate_processing(
                track_id, 0, "balanced", 0.5
            )
            assert ok

        assert len(worker._processor_cache) <= _PROCESSOR_CACHE_MAX

    @pytest.mark.asyncio
    async def test_preset_switches_are_bounded(self, worker, stub_processor):
        """Distinct presets on ONE track also count against the cap."""
        for i in range(_PROCESSOR_CACHE_MAX + 5):
            await worker._process_chunk(
                Mock(filepath="/tmp/t.wav"), 7, 0, f"preset{i}", 0.5, "tier1"
            )

        assert len(worker._processor_cache) == _PROCESSOR_CACHE_MAX


class TestBuildLockBound:
    """`_processor_build_locks` must not outgrow `_processor_cache` (#4369)."""

    @pytest.mark.asyncio
    async def test_locks_evicted_in_lockstep(self, worker, stub_processor):
        for track_id in range(_PROCESSOR_CACHE_MAX + 5):
            await worker._process_chunk(
                Mock(filepath="/tmp/t.wav"), track_id, 0, "balanced", 0.5, "tier1"
            )

        assert len(worker._processor_build_locks) <= len(worker._processor_cache)
        assert set(worker._processor_build_locks) == set(worker._processor_cache)

    @pytest.mark.asyncio
    async def test_failed_build_leaves_no_orphan_lock(self, worker):
        """A construction that raises must not strand its build lock."""

        def _boom(**kwargs):
            raise RuntimeError("cannot open file")

        with patch("core.streamlined_worker.Path") as mock_path, patch(
            "core.chunked_processor.ChunkedAudioProcessor", _boom
        ):
            mock_path.return_value.exists.return_value = True
            for track_id in range(20):
                result = await worker._process_chunk(
                    Mock(filepath="/tmp/t.wav"), track_id, 0, "balanced", 0.5, "tier1"
                )
                assert result is None

        assert worker._processor_cache == {}
        assert worker._processor_build_locks == {}
        assert worker._build_waiters == {}

    @pytest.mark.asyncio
    async def test_concurrent_waiters_keep_the_lock_alive(self, worker):
        """Two tasks on one cold key share one lock and build once."""
        import asyncio

        gate = asyncio.Event()
        built = []

        class _SlowProcessor:
            def __init__(self, **kwargs):
                built.append(kwargs)
                self.process_chunk_safe = AsyncMock(
                    return_value=("/tmp/chunk.wav", None)
                )

        def _blocking_ctor(**kwargs):
            # Runs inside asyncio.to_thread; block until the second caller is
            # queued on the build lock.
            asyncio.run_coroutine_threadsafe(_noop(), loop).result()
            return _SlowProcessor(**kwargs)

        async def _noop():
            await gate.wait()

        loop = asyncio.get_running_loop()

        with patch("core.streamlined_worker.Path") as mock_path, patch(
            "core.chunked_processor.ChunkedAudioProcessor", _blocking_ctor
        ):
            mock_path.return_value.exists.return_value = True
            track = Mock(filepath="/tmp/t.wav")
            first = asyncio.create_task(
                worker._process_chunk(track, 3, 0, "balanced", 0.5, "tier1")
            )
            await asyncio.sleep(0)  # let `first` reach the ctor
            second = asyncio.create_task(
                worker._process_chunk(track, 3, 1, "balanced", 0.5, "tier1")
            )
            await asyncio.sleep(0)  # let `second` queue on the build lock

            # While a build is in flight the lock must be retained.
            assert worker._build_waiters[(3, "balanced", 0.5)] == 2

            gate.set()
            await asyncio.gather(first, second)

        assert len(built) == 1, "the queued waiter rebuilt instead of reusing"
        assert worker._build_waiters == {}


class TestIntensityBucketing:
    """Slider drag must not mint a processor per intermediate float."""

    def test_intensity_key_matches_cached_chunk_granularity(self):
        # cache.manager.CachedChunk.key() formats intensity as `{:.1f}`, so the
        # chunk cache already treats these as one entry.
        assert _intensity_key(0.4951) == _intensity_key(0.5049) == 0.5
        assert _intensity_key(0.44) == 0.4
        assert _intensity_key(1.0) == 1.0

    @pytest.mark.asyncio
    async def test_slider_drag_produces_one_entry_per_bucket(
        self, worker, stub_processor
    ):
        """A 100-step drag over one 0.1 bucket builds a single processor."""
        for step in range(100):
            intensity = 0.50 + step * 0.00005  # 0.5000 .. 0.50495
            await worker._process_chunk(
                Mock(filepath="/tmp/t.wav"), 42, 0, "balanced", intensity, "tier1"
            )

        assert len(worker._processor_cache) == 1
        assert len(stub_processor.instances) == 1

    @pytest.mark.asyncio
    async def test_processor_built_at_the_bucketed_intensity(
        self, worker, stub_processor
    ):
        """The cached processor matches the key it is stored under."""
        await worker._process_chunk(
            Mock(filepath="/tmp/t.wav"), 42, 0, "balanced", 0.4951, "tier1"
        )

        (key,) = worker._processor_cache.keys()
        assert key == (42, "balanced", 0.5)
        assert stub_processor.instances[0].intensity == 0.5


class TestCloseOnEviction:
    """Evicted wrappers DO own a closable resource, as of #4737.

    This class previously asserted the opposite and carried the note "if this
    ever gains a close(), _remember_processor must be revisited". It did, and
    it was: ChunkedAudioProcessor now holds a SeekableSource, which for
    .m4a/.aac/.wma owns a temp WAV, so dropping an evicted entry without
    closing it leaks that file for the process lifetime. The tripwire fired
    exactly as intended; this is its updated form.
    """

    def test_chunked_processor_exposes_close(self):
        from core.chunked_processor import ChunkedAudioProcessor

        assert callable(getattr(ChunkedAudioProcessor, "close", None))

    def test_eviction_closes_the_evicted_processor(self, worker):
        """The #4521 bound and the #4737 cleanup have to hold together."""
        import core.streamlined_worker as sw

        closed = []

        class FakeProcessor:
            def __init__(self, tag: int) -> None:
                self.tag = tag

            def close(self) -> None:
                closed.append(self.tag)

        with patch.object(sw, "_PROCESSOR_CACHE_MAX", 2):
            for i in range(3):
                worker._remember_processor((i, None, 1.0), FakeProcessor(i))

        assert len(worker._processor_cache) == 2, "the #4521 bound must still hold"
        assert closed == [0], "the LRU-evicted processor must be closed"
