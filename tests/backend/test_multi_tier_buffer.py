"""
Tests for Multi-Tier Buffer Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the CPU-inspired hierarchical caching system with branch prediction.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import asyncio
import time
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from multi_tier_buffer import (
    CacheEntry,
    CacheTier,
    BranchPredictor,
    BranchScenario,
    MultiTierBufferManager,
    CHUNK_DURATION,
    AVAILABLE_PRESETS
)


class TestCacheEntry:
    """Tests for CacheEntry dataclass"""

    def test_cache_entry_creation(self):
        """Test creating a cache entry"""
        entry = CacheEntry(
            track_id=1,
            preset="adaptive",
            chunk_idx=0,
            intensity=1.0,
            timestamp=time.time()
        )

        assert entry.track_id == 1
        assert entry.preset == "adaptive"
        assert entry.chunk_idx == 0
        assert entry.access_count == 0

    def test_cache_entry_key_generation(self):
        """Test unique key generation"""
        entry = CacheEntry(
            track_id=1,
            preset="adaptive",
            chunk_idx=5,
            intensity=0.8,
            timestamp=time.time()
        )

        key = entry.key()
        assert "1_adaptive_0.8_5" == key

    def test_cache_entry_size(self):
        """Test size estimation"""
        entry = CacheEntry(
            track_id=1,
            preset="adaptive",
            chunk_idx=0,
            intensity=1.0,
            timestamp=time.time()
        )

        assert entry.size_mb() > 0


class TestCacheTier:
    """Tests for individual cache tier"""

    @pytest.mark.asyncio
    async def test_tier_initialization(self):
        """Test creating a cache tier"""
        tier = CacheTier("L1", 18.0)

        assert tier.name == "L1"
        assert tier.max_size_mb == 18.0
        assert tier.get_size_mb() == 0.0

    @pytest.mark.asyncio
    async def test_add_entry(self):
        """Test adding entry to tier"""
        tier = CacheTier("L1", 18.0)

        entry = CacheEntry(
            track_id=1,
            preset="adaptive",
            chunk_idx=0,
            intensity=1.0,
            timestamp=time.time()
        )

        result = await tier.add_entry(entry)

        assert result is True
        assert entry.key() in tier.entries
        assert tier.get_size_mb() > 0

    @pytest.mark.asyncio
    async def test_get_entry_updates_access_stats(self):
        """Test that getting entry updates access statistics"""
        tier = CacheTier("L1", 18.0)

        entry = CacheEntry(
            track_id=1,
            preset="adaptive",
            chunk_idx=0,
            intensity=1.0,
            timestamp=time.time()
        )

        await tier.add_entry(entry)

        retrieved = tier.get_entry(entry.key())
        assert retrieved is not None
        assert retrieved.access_count == 1

        # Access again
        retrieved = tier.get_entry(entry.key())
        assert retrieved.access_count == 2

    @pytest.mark.asyncio
    async def test_eviction_when_full(self):
        """Test that tier evicts entries when full"""
        tier = CacheTier("L1", 6.0)  # Small tier (2 chunks)

        # Add 3 entries (should evict oldest/lowest priority)
        for i in range(3):
            entry = CacheEntry(
                track_id=1,
                preset="adaptive",
                chunk_idx=i,
                intensity=1.0,
                timestamp=time.time(),
                probability=1.0 - (i * 0.2)  # Decreasing probability
            )
            await asyncio.sleep(0.01)  # Small delay for timestamp ordering
            await tier.add_entry(entry)

        # Should have evicted lowest probability entry
        assert len(tier.entries) <= 2
        assert tier.get_size_mb() <= 6.0

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing tier"""
        tier = CacheTier("L1", 18.0)

        entry = CacheEntry(
            track_id=1,
            preset="adaptive",
            chunk_idx=0,
            intensity=1.0,
            timestamp=time.time()
        )

        await tier.add_entry(entry)
        assert len(tier.entries) > 0

        tier.clear()
        assert len(tier.entries) == 0

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting tier statistics"""
        tier = CacheTier("L1", 18.0)

        # Empty stats
        stats = tier.get_stats()
        assert stats['size_mb'] == 0.0
        assert stats['count'] == 0

        # Add entry
        entry = CacheEntry(
            track_id=1,
            preset="adaptive",
            chunk_idx=0,
            intensity=1.0,
            timestamp=time.time()
        )
        await tier.add_entry(entry)

        stats = tier.get_stats()
        assert stats['size_mb'] > 0
        assert stats['count'] == 1
        assert 0 <= stats['utilization'] <= 1.0


class TestBranchPredictor:
    """Tests for branch prediction logic"""

    def test_predictor_initialization(self):
        """Test creating branch predictor"""
        predictor = BranchPredictor()

        assert len(predictor.transition_matrix) == 0
        assert predictor.predictions_made == 0

    def test_record_switch(self):
        """Test recording preset switches"""
        predictor = BranchPredictor()

        predictor.record_switch("adaptive", "punchy")

        assert ("adaptive", "punchy") in predictor.transition_matrix
        assert predictor.transition_matrix[("adaptive", "punchy")] == 1
        assert len(predictor.recent_switches) == 1

    def test_predict_next_presets_no_history(self):
        """Test prediction with no history (cold start)"""
        predictor = BranchPredictor()

        predictions = predictor.predict_next_presets("adaptive", top_n=3)

        assert len(predictions) == 3
        # Should return default presets
        assert all(isinstance(p, tuple) and len(p) == 2 for p in predictions)
        # Current preset should not be in predictions
        assert all(preset != "adaptive" for preset, _ in predictions)

    def test_predict_next_presets_with_history(self):
        """Test prediction with learned patterns"""
        predictor = BranchPredictor()

        # Record pattern: adaptive -> punchy (5 times)
        for _ in range(5):
            predictor.record_switch("adaptive", "punchy")

        # Record pattern: adaptive -> bright (2 times)
        for _ in range(2):
            predictor.record_switch("adaptive", "bright")

        predictions = predictor.predict_next_presets("adaptive", top_n=2)

        # "punchy" should be top prediction (5/7 = 71%)
        assert predictions[0][0] == "punchy"
        assert predictions[0][1] > predictions[1][1]  # Higher probability

    def test_predict_branches(self):
        """Test generating branch scenarios"""
        predictor = BranchPredictor()

        # Add some history
        predictor.record_switch("adaptive", "punchy")

        branches = predictor.predict_branches("adaptive", current_chunk=5, position=180.0)

        assert len(branches) > 0
        assert isinstance(branches[0], BranchScenario)

        # Should have "continue_current" scenario
        continue_branch = next((b for b in branches if b.name == "continue_current"), None)
        assert continue_branch is not None
        assert continue_branch.preset == "adaptive"

    def test_accuracy_tracking(self):
        """Test prediction accuracy metrics"""
        predictor = BranchPredictor()

        # Record correct prediction
        predictor.update_accuracy(True)
        assert predictor.get_accuracy() == 1.0

        # Record incorrect prediction
        predictor.update_accuracy(False)
        assert predictor.get_accuracy() == 0.5  # 1 correct, 1 incorrect


class TestMultiTierBufferManager:
    """Tests for the complete multi-tier system"""

    @pytest.mark.asyncio
    async def test_manager_initialization(self):
        """Test creating multi-tier buffer manager"""
        manager = MultiTierBufferManager()

        assert manager.l1_cache is not None
        assert manager.l2_cache is not None
        assert manager.l3_cache is not None
        assert manager.branch_predictor is not None

    @pytest.mark.asyncio
    async def test_position_update(self):
        """Test updating playback position"""
        manager = MultiTierBufferManager()

        await manager.update_position(
            track_id=1,
            position=30.0,
            preset="adaptive",
            intensity=1.0
        )

        assert manager.current_track_id == 1
        assert manager.current_position == 30.0
        assert manager.current_preset == "adaptive"

    @pytest.mark.asyncio
    async def test_track_change_clears_caches(self):
        """Test that changing tracks clears old caches"""
        manager = MultiTierBufferManager()

        # Set up initial track
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        # Check that track 1 chunks are cached
        track_1_entry_found = any(
            entry.track_id == 1 for entry in manager.l1_cache.entries.values()
        )
        assert track_1_entry_found

        # Change track
        await manager.update_position(track_id=2, position=0.0, preset="adaptive", intensity=1.0)

        # Old track caches should be cleared, new track should be cached
        track_1_still_cached = any(
            entry.track_id == 1 for entry in manager.l1_cache.entries.values()
        )
        track_2_cached = any(
            entry.track_id == 2 for entry in manager.l1_cache.entries.values()
        )

        assert not track_1_still_cached  # Old track cleared
        assert track_2_cached  # New track cached

    @pytest.mark.asyncio
    async def test_preset_switch_recorded(self):
        """Test that preset switches are recorded in predictor"""
        manager = MultiTierBufferManager()

        # Initial position
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        # Switch preset
        await manager.update_position(track_id=1, position=10.0, preset="punchy", intensity=1.0)

        # Should have recorded transition
        assert ("adaptive", "punchy") in manager.branch_predictor.transition_matrix

    @pytest.mark.asyncio
    async def test_l1_cache_updates(self):
        """Test that L1 cache is populated correctly"""
        manager = MultiTierBufferManager()

        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        # L1 should have current + next chunk for top presets
        assert len(manager.l1_cache.entries) > 0

        # Current chunk (0) for adaptive should be cached
        is_cached, tier = manager.is_chunk_cached(1, "adaptive", 0, 1.0)
        assert is_cached is True

    @pytest.mark.asyncio
    async def test_cache_hit_tracking(self):
        """Test cache hit/miss tracking"""
        manager = MultiTierBufferManager()

        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        # Check cached chunk (should hit)
        is_cached, tier = manager.is_chunk_cached(1, "adaptive", 0, 1.0)
        assert is_cached is True
        assert manager.l1_hits > 0

        # Check non-existent chunk (should miss)
        is_cached, tier = manager.is_chunk_cached(1, "adaptive", 999, 1.0)
        assert is_cached is False
        assert manager.l1_misses > 0

    @pytest.mark.asyncio
    async def test_get_cache_stats(self):
        """Test getting comprehensive cache statistics"""
        manager = MultiTierBufferManager()

        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        stats = manager.get_cache_stats()

        assert 'l1' in stats
        assert 'l2' in stats
        assert 'l3' in stats
        assert 'overall' in stats
        assert 'prediction' in stats

        # Check that stats have expected keys
        assert 'hit_rate' in stats['l1']
        assert 'size_mb' in stats['l1']
        assert 'total_hits' in stats['overall']

    @pytest.mark.asyncio
    async def test_clear_all_caches(self):
        """Test clearing all cache tiers"""
        manager = MultiTierBufferManager()

        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        # Should have some cached entries
        initial_l1_count = len(manager.l1_cache.entries)
        assert initial_l1_count > 0

        manager.clear_all_caches()

        assert len(manager.l1_cache.entries) == 0
        assert len(manager.l2_cache.entries) == 0
        assert len(manager.l3_cache.entries) == 0

    @pytest.mark.asyncio
    async def test_chunk_calculation(self):
        """Test chunk index calculation from position"""
        manager = MultiTierBufferManager()

        # Position 0s -> chunk 0
        assert manager._get_current_chunk(0.0) == 0

        # Position 30s -> chunk 1
        assert manager._get_current_chunk(30.0) == 1

        # Position 60s -> chunk 2
        assert manager._get_current_chunk(60.0) == 2

        # Position 45s -> chunk 1
        assert manager._get_current_chunk(45.0) == 1


class TestIntegrationScenarios:
    """Integration tests for realistic usage scenarios"""

    @pytest.mark.asyncio
    async def test_typical_playback_flow(self):
        """Test typical user playback behavior"""
        manager = MultiTierBufferManager()

        # User starts playing
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        # Playback advances
        await manager.update_position(track_id=1, position=15.0, preset="adaptive", intensity=1.0)

        # User switches preset
        await manager.update_position(track_id=1, position=45.0, preset="punchy", intensity=1.0)

        # Check stats
        stats = manager.get_cache_stats()
        assert stats['overall']['total_size_mb'] > 0
        assert stats['prediction']['switches_in_session'] == 1

    @pytest.mark.asyncio
    async def test_exploration_mode(self):
        """Test user rapidly switching presets (exploration)"""
        manager = MultiTierBufferManager()

        presets_to_try = ["adaptive", "gentle", "warm", "bright", "punchy", "adaptive"]

        for i, preset in enumerate(presets_to_try):
            await manager.update_position(
                track_id=1,
                position=i * 10.0,
                preset=preset,
                intensity=1.0
            )

        # Should have recorded multiple switches
        assert manager.preset_switches_in_session == len(presets_to_try) - 1

    @pytest.mark.asyncio
    async def test_settled_mode(self):
        """Test user staying on one preset (settled)"""
        manager = MultiTierBufferManager()

        # User stays on "adaptive" for entire track
        for position in range(0, 180, 15):  # 3 minutes, 15s intervals
            await manager.update_position(
                track_id=1,
                position=float(position),
                preset="adaptive",
                intensity=1.0
            )

        # Should have no preset switches
        assert manager.preset_switches_in_session == 0

        # L3 should have deep buffer for "adaptive"
        stats = manager.get_cache_stats()
        assert stats['l3']['count'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
