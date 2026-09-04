"""
Tests for Streamlined Cache Manager (Beta.9)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the simplified two-tier cache system.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

NOTE (#4691): this module carried a blanket module-level skip reading "Tests
use APIs incompatible with current implementation". It was not true of the
module — 20 of its 24 tests passed against the current API the whole time. The
four that did not were asserting a 30-second chunk model (60s -> 2 chunks,
position 30.0 -> chunk 1) that the live 15s/10s overlap geometry has not
matched for a long time. Those four now compare against
``chunk_boundaries``' ``chunk_for_position()`` / ``content_chunk_count()``, the
single sources of truth the implementation itself delegates to, so the same
drift cannot silently reopen.

This is the only dedicated coverage for the streamlined cache manager, which
``config/startup.py`` treats as a critical worker — it was reporting green over
zero executing assertions.
"""

import asyncio

import pytest

# Add backend to path
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_boundaries import chunk_for_position, content_chunk_count
from cache.manager import (
    CHUNK_DURATION,
    CHUNK_SIZE_MB,
    CachedChunk,
    StreamlinedCacheManager,
    TrackCacheStatus,
)


class TestCachedChunk:
    """Test CachedChunk dataclass."""

    def test_cached_chunk_creation(self):
        """Test creating a cached chunk."""
        chunk = CachedChunk(
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
            chunk_path=Path("/tmp/chunk.webm")
        )

        assert chunk.track_id == 1
        assert chunk.chunk_idx == 0
        assert chunk.preset == "adaptive"
        assert chunk.intensity == 1.0
        assert chunk.chunk_path == Path("/tmp/chunk.webm")
        assert chunk.access_count == 0

    def test_cached_chunk_key(self):
        """Test cache key generation.

        #5251: the key now carries a trailing file_signature segment
        (empty string when none is supplied) so an in-place file edit
        produces a different key rather than reusing a stale one.
        """
        chunk = CachedChunk(
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
            chunk_path=Path("/tmp/chunk.webm")
        )

        key = chunk.key()
        assert key == "1_adaptive_1.0_0_"

    def test_cached_chunk_key_original(self):
        """Test cache key for original (unprocessed) chunk."""
        chunk = CachedChunk(
            track_id=1,
            chunk_idx=0,
            preset=None,  # Original
            intensity=1.0,
            chunk_path=Path("/tmp/chunk.webm")
        )

        key = chunk.key()
        assert key == "1_original_1.0_0_"

    def test_cached_chunk_key_includes_file_signature(self):
        """#5251: two chunks that differ only in file_signature must get
        different keys — this is the whole point of the fix."""
        base_kwargs = dict(
            track_id=1, chunk_idx=0, preset="adaptive", intensity=1.0,
            chunk_path=Path("/tmp/chunk.webm")
        )
        chunk_a = CachedChunk(file_signature="aaaaaaaa", **base_kwargs)
        chunk_b = CachedChunk(file_signature="bbbbbbbb", **base_kwargs)

        assert chunk_a.key() != chunk_b.key()
        assert chunk_a.key() == "1_adaptive_1.0_0_aaaaaaaa"
        assert chunk_b.key() == "1_adaptive_1.0_0_bbbbbbbb"

    def test_is_original(self):
        """Test checking if chunk is original."""
        original = CachedChunk(
            track_id=1, chunk_idx=0, preset=None, intensity=1.0,
            chunk_path=Path("/tmp/chunk.webm")
        )
        processed = CachedChunk(
            track_id=1, chunk_idx=0, preset="adaptive", intensity=1.0,
            chunk_path=Path("/tmp/chunk.webm")
        )

        assert original.is_original() is True
        assert processed.is_original() is False

    def test_mark_accessed(self):
        """Test access tracking."""
        chunk = CachedChunk(
            track_id=1, chunk_idx=0, preset="adaptive", intensity=1.0,
            chunk_path=Path("/tmp/chunk.webm")
        )

        assert chunk.access_count == 0
        initial_time = chunk.last_access

        chunk.mark_accessed()
        assert chunk.access_count == 1
        assert chunk.last_access >= initial_time


class TestTrackCacheStatus:
    """Test TrackCacheStatus dataclass."""

    def test_track_cache_status_creation(self):
        """Test creating track cache status."""
        status = TrackCacheStatus(track_id=1, total_chunks=10)

        assert status.track_id == 1
        assert status.total_chunks == 10
        assert len(status.cached_chunks_original) == 0
        assert len(status.cached_chunks_processed) == 0
        assert status.cache_complete is False

    def test_completion_percent(self):
        """Test cache completion percentage calculation."""
        status = TrackCacheStatus(track_id=1, total_chunks=10)

        # 0% complete
        assert status.get_completion_percent() == 0.0

        # 50% complete
        status.cached_chunks_processed.update([0, 1, 2, 3, 4])
        assert status.get_completion_percent() == 50.0

        # 100% complete
        status.cached_chunks_processed.update([5, 6, 7, 8, 9])
        assert status.get_completion_percent() == 100.0

    def test_is_fully_cached(self):
        """Test checking if track is fully cached."""
        status = TrackCacheStatus(track_id=1, total_chunks=3)

        # Not fully cached
        assert status.is_fully_cached() is False

        # Original cached, processed not cached
        status.cached_chunks_original.update([0, 1, 2])
        assert status.is_fully_cached() is False

        # Both cached
        status.cached_chunks_processed.update([0, 1, 2])
        assert status.is_fully_cached() is True


class TestStreamlinedCacheManager:
    """Test StreamlinedCacheManager."""

    @pytest.fixture
    def cache_manager(self):
        """Create a fresh cache manager for each test."""
        return StreamlinedCacheManager()

    def test_initialization(self, cache_manager):
        """Test cache manager initialization."""
        assert cache_manager.current_track_id is None
        assert cache_manager.current_position == 0.0
        assert cache_manager.current_preset == "adaptive"
        assert cache_manager.intensity == 1.0
        assert cache_manager.auto_mastering_enabled is True
        assert len(cache_manager.tier1_cache) == 0
        assert len(cache_manager.tier2_cache) == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("position", [0.0, 15.0, 30.0, 45.0, 60.0, 90.0])
    async def test_get_current_chunk(self, cache_manager, position):
        """Chunk index comes from the chunk-model SoT, not a local formula.

        These assertions used to hardcode a 30-second chunk model
        (`_get_current_chunk(30.0) == 1`), which the live 15s/10s overlap model
        has not matched for a long time; the drift was invisible because the
        module was skipped (#4691). Comparing against `chunk_for_position()`
        pins what `_get_current_chunk` actually promises — that it delegates —
        without re-encoding a geometry that can change again.

        A track has to be loaded first: with none, the manager falls back to
        `total_chunks = 1` and every position maps to chunk 0, which is what
        made the original run report `_get_current_chunk(30.0) == 0`.
        """
        duration = 120.0
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, duration)
        total = cache_manager.track_status[1].total_chunks

        assert cache_manager._get_current_chunk(position) == chunk_for_position(position, total)[0]

    @pytest.mark.asyncio
    async def test_get_current_chunk_is_zero_based_and_monotonic(self, cache_manager):
        """Anchor the delegation to facts, so it cannot pass vacuously."""
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, 120.0)

        assert cache_manager._get_current_chunk(0.0) == 0
        # Chunk 0 emits a full CHUNK_DURATION, so a position comfortably inside
        # it maps there. NOT every position inside it: within
        # SEEK_MIN_CHUNK_REMAINDER of the chunk end, chunk_for_position()
        # deliberately advances to the next chunk rather than hand back a
        # sliver that underruns immediately — asserting `CHUNK_DURATION - 0.1`
        # maps to 0 fails, correctly.
        assert cache_manager._get_current_chunk(CHUNK_DURATION - 1.0) == 0
        assert cache_manager._get_current_chunk(CHUNK_DURATION - 0.1) == 1

        indices = [cache_manager._get_current_chunk(p) for p in (0.0, 30.0, 60.0, 90.0)]
        assert indices == sorted(indices)
        assert indices[-1] > indices[0]

    def test_get_current_chunk_without_a_track_maps_everything_to_zero(self, cache_manager):
        """The documented fallback: no track status means total_chunks == 1."""
        assert cache_manager.current_track_id is None
        assert cache_manager._get_current_chunk(90.0) == 0

    @pytest.mark.parametrize("duration", [15.0, 60.0, 65.0, 90.5])
    def test_calculate_total_chunks(self, cache_manager, duration):
        """Total chunks delegates to content_chunk_count() (#4620).

        The old expectations (60s -> 2, 65s -> 3, 90.5s -> 4) encoded a 30s
        chunk model. The cache-completion target must equal
        ``ChunkedAudioProcessor.total_chunks``, which is set from
        ``content_chunk_count()``, so that is what this compares against —
        re-deriving the number here is exactly how the two drifted apart.
        """
        assert cache_manager._calculate_total_chunks(duration) == content_chunk_count(duration)

    def test_calculate_total_chunks_is_at_least_one_and_monotonic(self, cache_manager):
        """The properties the delegation must preserve regardless of geometry."""
        assert cache_manager._calculate_total_chunks(1.0) >= 1
        counts = [cache_manager._calculate_total_chunks(d) for d in (15.0, 60.0, 90.5, 300.0)]
        assert counts == sorted(counts)

    @pytest.mark.asyncio
    async def test_update_position_initializes_track(self, cache_manager):
        """Test position update initializes track status."""
        await cache_manager.update_position(
            track_id=1,
            position=0.0,
            preset="adaptive",
            intensity=1.0,
            track_duration=90.0
        )

        assert cache_manager.current_track_id == 1
        assert cache_manager.current_position == 0.0
        assert 1 in cache_manager.track_status
        # Was hardcoded to 3, a 30s-chunk-model number (#4691).
        assert cache_manager.track_status[1].total_chunks == content_chunk_count(90.0)

    @pytest.mark.asyncio
    async def test_update_position_clears_tier1_on_track_change(self, cache_manager):
        """Test Tier 1 cache clears on track change."""
        # Add chunk to Tier 1
        chunk = CachedChunk(
            track_id=1, chunk_idx=0, preset="adaptive", intensity=1.0,
            chunk_path=Path("/tmp/chunk.webm")
        )
        await cache_manager.add_chunk(1, 0, Path("/tmp/chunk.webm"), "adaptive", 1.0, tier="tier1")

        assert len(cache_manager.tier1_cache) == 1

        # Change track
        await cache_manager.update_position(
            track_id=2,
            position=0.0,
            preset="adaptive",
            intensity=1.0,
            track_duration=60.0
        )

        # Tier 1 should be cleared
        assert len(cache_manager.tier1_cache) == 0

    @pytest.mark.asyncio
    async def test_get_chunk_tier1_hit(self, cache_manager):
        """Test getting chunk from Tier 1."""
        chunk_path = Path("/tmp/chunk_0.webm")
        await cache_manager.add_chunk(1, 0, chunk_path, "adaptive", 1.0, tier="tier1")

        result_path, tier = await cache_manager.get_chunk(1, 0, "adaptive", 1.0)

        assert result_path == chunk_path
        assert tier == "tier1"
        assert cache_manager.tier1_hits == 1
        assert cache_manager.tier1_misses == 0

    @pytest.mark.asyncio
    async def test_get_chunk_tier2_hit(self, cache_manager):
        """Test getting chunk from Tier 2."""
        chunk_path = Path("/tmp/chunk_5.webm")
        await cache_manager.add_chunk(1, 5, chunk_path, "adaptive", 1.0, tier="tier2")

        result_path, tier = await cache_manager.get_chunk(1, 5, "adaptive", 1.0)

        assert result_path == chunk_path
        assert tier == "tier2"
        assert cache_manager.tier2_hits == 1
        assert cache_manager.tier1_misses == 0  # Tier 2 miss doesn't count as Tier 1 miss

    @pytest.mark.asyncio
    async def test_get_chunk_miss(self, cache_manager):
        """Test cache miss."""
        result_path, tier = await cache_manager.get_chunk(1, 0, "adaptive", 1.0)

        assert result_path is None
        assert tier == "miss"
        assert cache_manager.tier1_misses == 1

    @pytest.mark.asyncio
    async def test_get_chunk_signature_mismatch_is_a_miss(self, cache_manager):
        """#5251: a chunk cached under one file_signature must not be served
        for a lookup under a different one — the exact scenario an in-place
        file edit (same track_id, new content) produces."""
        chunk_path = Path("/tmp/chunk_0.webm")
        await cache_manager.add_chunk(
            1, 0, chunk_path, "adaptive", 1.0, tier="tier1", file_signature="aaaaaaaa"
        )

        # Same track/chunk/preset/intensity, different signature (as if the
        # source file were edited since this chunk was cached).
        result_path, tier = await cache_manager.get_chunk(
            1, 0, "adaptive", 1.0, file_signature="bbbbbbbb"
        )

        assert result_path is None
        assert tier == "miss"

        # The original signature still hits, proving this is a genuine
        # signature check and not an accidental full-miss.
        result_path, tier = await cache_manager.get_chunk(
            1, 0, "adaptive", 1.0, file_signature="aaaaaaaa"
        )
        assert result_path == chunk_path
        assert tier == "tier1"

    @pytest.mark.asyncio
    async def test_add_chunk_tier1_auto_detect(self, cache_manager):
        """Test auto-detection of Tier 1 chunks."""
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, 60.0)

        # Current chunk (0) should go to Tier 1
        await cache_manager.add_chunk(1, 0, Path("/tmp/chunk_0.webm"), "adaptive", 1.0, tier="auto")
        assert "1_adaptive_1.0_0_" in cache_manager.tier1_cache

        # Next chunk (1) should go to Tier 1
        await cache_manager.add_chunk(1, 1, Path("/tmp/chunk_1.webm"), "adaptive", 1.0, tier="auto")
        assert "1_adaptive_1.0_1_" in cache_manager.tier1_cache

        # Chunk 5 should go to Tier 2
        await cache_manager.add_chunk(1, 5, Path("/tmp/chunk_5.webm"), "adaptive", 1.0, tier="auto")
        assert "1_adaptive_1.0_5_" in cache_manager.tier2_cache

    @pytest.mark.asyncio
    async def test_tier1_eviction(self, cache_manager):
        """Test Tier 1 LRU eviction."""
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, 60.0)

        # Fill Tier 1 (max 4 chunks: 2 positions × 2 states)
        for i in range(5):
            await cache_manager.add_chunk(1, i, Path(f"/tmp/chunk_{i}.webm"), "adaptive", 1.0, tier="tier1")

        # Should have evicted oldest entry
        assert len(cache_manager.tier1_cache) == 4

    @pytest.mark.asyncio
    async def test_tier2_track_status_updates(self, cache_manager):
        """Test Tier 2 updates track status."""
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, 90.0)

        # Add original chunk
        await cache_manager.add_chunk(1, 0, Path("/tmp/chunk_0_orig.webm"), None, 1.0, tier="tier2")
        assert 0 in cache_manager.track_status[1].cached_chunks_original

        # Add processed chunk
        await cache_manager.add_chunk(1, 0, Path("/tmp/chunk_0_proc.webm"), "adaptive", 1.0, tier="tier2")
        assert 0 in cache_manager.track_status[1].cached_chunks_processed

    @pytest.mark.asyncio
    async def test_track_fully_cached_detection(self, cache_manager):
        """Test detection of fully cached track.

        The chunk count is taken from the chunk model rather than assumed to
        be 2 (#4691): a 60s track is 6 content chunks under the live 15s/10s
        geometry, so the old fixed pair of add_chunk calls could never reach
        "fully cached" and the assertion silently depended on a stale model.
        """
        duration = 60.0
        total = content_chunk_count(duration)
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, duration)

        # Add all original chunks
        for idx in range(total):
            await cache_manager.add_chunk(
                1, idx, Path(f"/tmp/c{idx}_o.webm"), None, 1.0, tier="tier2"
            )

        assert cache_manager.is_track_fully_cached(1) is False

        # Add all processed chunks
        for idx in range(total):
            await cache_manager.add_chunk(
                1, idx, Path(f"/tmp/c{idx}_p.webm"), "adaptive", 1.0, tier="tier2"
            )

        assert cache_manager.is_track_fully_cached(1) is True

    @pytest.mark.asyncio
    async def test_get_stats(self, cache_manager):
        """Test cache statistics."""
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, 60.0)

        # Add some chunks
        await cache_manager.add_chunk(1, 0, Path("/tmp/c0.webm"), "adaptive", 1.0, tier="tier1")
        await cache_manager.add_chunk(1, 5, Path("/tmp/c5.webm"), "adaptive", 1.0, tier="tier2")

        # Generate some hits/misses
        await cache_manager.get_chunk(1, 0, "adaptive", 1.0)  # Tier 1 hit
        await cache_manager.get_chunk(1, 5, "adaptive", 1.0)  # Tier 2 hit
        await cache_manager.get_chunk(1, 10, "adaptive", 1.0)  # Miss

        stats = cache_manager.get_stats()

        assert stats["tier1"]["chunks"] == 1
        assert stats["tier1"]["hits"] == 1
        assert stats["tier1"]["misses"] == 1
        assert stats["tier2"]["chunks"] == 1
        assert stats["tier2"]["hits"] == 1
        assert stats["overall"]["total_chunks"] == 2
        assert 1 in stats["tracks"]

    @pytest.mark.asyncio
    async def test_clear_all(self, cache_manager):
        """Test clearing all caches."""
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, 60.0)

        # Add chunks
        await cache_manager.add_chunk(1, 0, Path("/tmp/c0.webm"), "adaptive", 1.0, tier="tier1")
        await cache_manager.add_chunk(1, 5, Path("/tmp/c5.webm"), "adaptive", 1.0, tier="tier2")

        assert len(cache_manager.tier1_cache) == 1
        assert len(cache_manager.tier2_cache) == 1
        assert len(cache_manager.track_status) == 1

        await cache_manager.clear_all()

        assert len(cache_manager.tier1_cache) == 0
        assert len(cache_manager.tier2_cache) == 0
        assert len(cache_manager.track_status) == 0

    @pytest.mark.asyncio
    async def test_clear_all_deletes_on_disk_chunk_files(self, cache_manager, tmp_path):
        """#5249: clear_all() must delete the on-disk WAV files, not just
        empty the in-memory dicts — otherwise ChunkPathCache's independent
        on-disk existence check keeps finding and serving the same bytes."""
        c1 = tmp_path / "c0.wav"
        c2 = tmp_path / "c5.wav"
        c1.write_bytes(b"fake-wav-bytes-1")
        c2.write_bytes(b"fake-wav-bytes-2")

        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, 60.0)
        await cache_manager.add_chunk(1, 0, c1, "adaptive", 1.0, tier="tier1")
        await cache_manager.add_chunk(1, 5, c2, "adaptive", 1.0, tier="tier2")

        assert c1.exists() and c2.exists()

        await cache_manager.clear_all()

        assert not c1.exists(), "clear_all() left a tier1 chunk file on disk"
        assert not c2.exists(), "clear_all() left a tier2 chunk file on disk"

    @pytest.mark.asyncio
    async def test_clear_track_deletes_on_disk_chunk_files(self, cache_manager, tmp_path):
        """#5249: same guarantee as clear_all(), but scoped to one track —
        and must NOT touch another track's still-cached files."""
        mine = tmp_path / "mine.wav"
        other = tmp_path / "other.wav"
        mine.write_bytes(b"fake-wav-bytes")
        other.write_bytes(b"fake-wav-bytes")

        await cache_manager.add_chunk(1, 0, mine, "adaptive", 1.0, tier="tier2")
        await cache_manager.add_chunk(2, 0, other, "adaptive", 1.0, tier="tier2")

        removed = await cache_manager.clear_track(1)

        assert removed == 1
        assert not mine.exists(), "clear_track() left the target track's chunk file on disk"
        assert other.exists(), "clear_track() deleted an unrelated track's chunk file"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("unrelated_track_id", [12, 21, 100, 512])
    async def test_clear_track_uses_exact_track_id_for_tier1(
        self, cache_manager, tmp_path, unrelated_track_id
    ):
        """#5250: clearing track 1 must not evict Tier 1 entries whose IDs
        merely contain the digit 1."""
        target_paths = [tmp_path / "track-1-a.wav", tmp_path / "track-1-b.wav"]
        unrelated_path = tmp_path / f"track-{unrelated_track_id}.wav"

        for path in (*target_paths, unrelated_path):
            path.write_bytes(b"fake-wav-bytes")

        for chunk_idx, path in enumerate(target_paths):
            await cache_manager.add_chunk(1, chunk_idx, path, tier="tier1")
        await cache_manager.add_chunk(unrelated_track_id, 0, unrelated_path, tier="tier1")

        removed = await cache_manager.clear_track(1)

        assert removed == len(target_paths)
        assert all(not path.exists() for path in target_paths)
        assert unrelated_path.exists()
        assert {chunk.track_id for chunk in cache_manager.tier1_cache.values()} == {
            unrelated_track_id
        }

    @pytest.mark.asyncio
    async def test_clear_track_tolerates_already_missing_file(self, cache_manager):
        """A chunk file that's already gone (race with another cleanup pass,
        or was never actually written) must not raise — matches this
        cache's established graceful-degradation style."""
        await cache_manager.add_chunk(
            1, 0, Path("/nonexistent/does_not_exist.wav"), "adaptive", 1.0, tier="tier1"
        )

        removed = await cache_manager.clear_track(1)  # must not raise

        assert removed == 1


class TestCacheMemoryManagement:
    """Test cache memory management."""

    @pytest.fixture
    def cache_manager(self):
        """Create a fresh cache manager for each test."""
        return StreamlinedCacheManager()

    @pytest.mark.asyncio
    async def test_tier2_evicts_oldest_track(self, cache_manager):
        """Test Tier 2 evicts oldest track when full."""
        # Add chunks for track 1 (fill Tier 2)
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, 300.0)  # 10 chunks

        for i in range(10):
            await cache_manager.add_chunk(1, i, Path(f"/tmp/t1_c{i}.webm"), "adaptive", 1.0, tier="tier2")

        # Switch to track 2 and fill more
        await cache_manager.update_position(2, 0.0, "adaptive", 1.0, 300.0)

        for i in range(10):
            await cache_manager.add_chunk(2, i, Path(f"/tmp/t2_c{i}.webm"), "adaptive", 1.0, tier="tier2")

        # Add many chunks for track 3 (should evict track 1, not current track 2)
        await cache_manager.update_position(3, 0.0, "adaptive", 1.0, 600.0)

        for i in range(50):
            await cache_manager.add_chunk(3, i, Path(f"/tmp/t3_c{i}.webm"), "adaptive", 1.0, tier="tier2")

        # Track 1 should be evicted (oldest, not current)
        # Track 2 might still be there
        # Track 3 should definitely be there (current)
        track_ids = set(chunk.track_id for chunk in cache_manager.tier2_cache.values())
        assert 3 in track_ids  # Current track protected
        # Track 1 may or may not be there depending on eviction

    @pytest.mark.asyncio
    async def test_original_and_processed_separate_cache_keys(self, cache_manager):
        """Test original and processed chunks have different cache keys."""
        await cache_manager.add_chunk(1, 0, Path("/tmp/c0_orig.webm"), None, 1.0, tier="tier1")
        await cache_manager.add_chunk(1, 0, Path("/tmp/c0_proc.webm"), "adaptive", 1.0, tier="tier1")

        # Both should be cached separately
        orig_path, tier = await cache_manager.get_chunk(1, 0, None, 1.0)
        proc_path, tier = await cache_manager.get_chunk(1, 0, "adaptive", 1.0)

        assert orig_path == Path("/tmp/c0_orig.webm")
        assert proc_path == Path("/tmp/c0_proc.webm")
        assert len(cache_manager.tier1_cache) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
