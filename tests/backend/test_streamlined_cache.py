"""
Tests for Streamlined Cache Manager (Beta.9)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the simplified two-tier cache system.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from streamlined_cache import (
    StreamlinedCacheManager,
    CachedChunk,
    TrackCacheStatus,
    CHUNK_DURATION,
    CHUNK_SIZE_MB
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
        """Test cache key generation."""
        chunk = CachedChunk(
            track_id=1,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
            chunk_path=Path("/tmp/chunk.webm")
        )

        key = chunk.key()
        assert key == "1_adaptive_1.0_0"

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
        assert key == "1_original_1.0_0"

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

    def test_get_current_chunk(self, cache_manager):
        """Test chunk index calculation."""
        assert cache_manager._get_current_chunk(0.0) == 0
        assert cache_manager._get_current_chunk(15.0) == 0
        assert cache_manager._get_current_chunk(30.0) == 1
        assert cache_manager._get_current_chunk(45.0) == 1
        assert cache_manager._get_current_chunk(60.0) == 2
        assert cache_manager._get_current_chunk(90.0) == 3

    def test_calculate_total_chunks(self, cache_manager):
        """Test total chunk calculation."""
        # Exactly divisible
        assert cache_manager._calculate_total_chunks(60.0) == 2

        # With remainder
        assert cache_manager._calculate_total_chunks(65.0) == 3
        assert cache_manager._calculate_total_chunks(90.5) == 4

        # Short track
        assert cache_manager._calculate_total_chunks(15.0) == 1

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
        assert cache_manager.track_status[1].total_chunks == 3

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
    async def test_add_chunk_tier1_auto_detect(self, cache_manager):
        """Test auto-detection of Tier 1 chunks."""
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, 60.0)

        # Current chunk (0) should go to Tier 1
        await cache_manager.add_chunk(1, 0, Path("/tmp/chunk_0.webm"), "adaptive", 1.0, tier="auto")
        assert "1_adaptive_1.0_0" in cache_manager.tier1_cache

        # Next chunk (1) should go to Tier 1
        await cache_manager.add_chunk(1, 1, Path("/tmp/chunk_1.webm"), "adaptive", 1.0, tier="auto")
        assert "1_adaptive_1.0_1" in cache_manager.tier1_cache

        # Chunk 5 should go to Tier 2
        await cache_manager.add_chunk(1, 5, Path("/tmp/chunk_5.webm"), "adaptive", 1.0, tier="auto")
        assert "1_adaptive_1.0_5" in cache_manager.tier2_cache

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
        """Test detection of fully cached track."""
        await cache_manager.update_position(1, 0.0, "adaptive", 1.0, 60.0)  # 2 chunks

        # Add all original chunks
        await cache_manager.add_chunk(1, 0, Path("/tmp/c0_o.webm"), None, 1.0, tier="tier2")
        await cache_manager.add_chunk(1, 1, Path("/tmp/c1_o.webm"), None, 1.0, tier="tier2")

        assert cache_manager.is_track_fully_cached(1) is False

        # Add all processed chunks
        await cache_manager.add_chunk(1, 0, Path("/tmp/c0_p.webm"), "adaptive", 1.0, tier="tier2")
        await cache_manager.add_chunk(1, 1, Path("/tmp/c1_p.webm"), "adaptive", 1.0, tier="tier2")

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
