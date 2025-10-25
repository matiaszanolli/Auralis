"""
End-to-End Integration Tests for Multi-Tier Buffer System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the complete integration with actual components.

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

from multi_tier_buffer import MultiTierBufferManager
from multi_tier_worker import MultiTierBufferWorker


class MockLibraryManager:
    """Mock library manager for testing"""

    class TracksRepository:
        def get_by_id(self, track_id):
            """Mock track retrieval"""
            from unittest.mock import Mock
            track = Mock()
            track.id = track_id
            track.filepath = f"/mock/path/track{track_id}.mp3"
            track.title = f"Test Track {track_id}"
            return track

    def __init__(self):
        self.tracks = self.TracksRepository()


class TestEndToEndIntegration:
    """End-to-end integration tests"""

    @pytest.mark.asyncio
    async def test_manager_and_worker_initialization(self):
        """Test that manager and worker can be initialized together"""
        manager = MultiTierBufferManager()
        library = MockLibraryManager()

        worker = MultiTierBufferWorker(
            buffer_manager=manager,
            library_manager=library
        )

        assert worker.buffer_manager is manager
        assert worker.library_manager is library

    @pytest.mark.asyncio
    async def test_worker_start_stop(self):
        """Test worker lifecycle"""
        manager = MultiTierBufferManager()
        library = MockLibraryManager()
        worker = MultiTierBufferWorker(manager, library)

        # Start worker
        await worker.start()
        assert worker.running is True

        # Give it a moment to initialize
        await asyncio.sleep(0.1)

        # Stop worker
        await worker.stop()
        assert worker.running is False

    @pytest.mark.asyncio
    async def test_position_updates_trigger_cache_population(self):
        """Test that position updates populate caches"""
        manager = MultiTierBufferManager()

        # Initial state - all caches empty
        assert len(manager.l1_cache.entries) == 0
        assert len(manager.l2_cache.entries) == 0
        assert len(manager.l3_cache.entries) == 0

        # Update position - should populate caches
        await manager.update_position(
            track_id=1,
            position=0.0,
            preset="adaptive",
            intensity=1.0
        )

        # L1 should have entries now
        assert len(manager.l1_cache.entries) > 0

        # L2 should have branch scenarios
        assert len(manager.l2_cache.entries) > 0

        # L3 should have long-term buffer
        assert len(manager.l3_cache.entries) > 0

    @pytest.mark.asyncio
    async def test_preset_switch_recorded_in_predictor(self):
        """Test that preset switches are learned"""
        manager = MultiTierBufferManager()

        # Start with adaptive
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        # Switch to punchy
        await manager.update_position(track_id=1, position=10.0, preset="punchy", intensity=1.0)

        # Check that transition was recorded
        assert ("adaptive", "punchy") in manager.branch_predictor.transition_matrix
        assert manager.branch_predictor.transition_matrix[("adaptive", "punchy")] == 1

        # Switch again
        await manager.update_position(track_id=1, position=20.0, preset="adaptive", intensity=1.0)
        await manager.update_position(track_id=1, position=30.0, preset="punchy", intensity=1.0)

        # Should have incremented
        assert manager.branch_predictor.transition_matrix[("adaptive", "punchy")] == 2

    @pytest.mark.asyncio
    async def test_predictions_improve_with_learning(self):
        """Test that predictions become more accurate with use"""
        manager = MultiTierBufferManager()

        # Establish pattern: adaptive -> punchy (5 times)
        for i in range(5):
            await manager.update_position(track_id=1, position=float(i*20), preset="adaptive", intensity=1.0)
            await manager.update_position(track_id=1, position=float(i*20 + 10), preset="punchy", intensity=1.0)

        # Now get predictions from adaptive
        predictions = manager.branch_predictor.predict_next_presets("adaptive", top_n=3)

        # Punchy should be top prediction
        assert len(predictions) > 0
        assert predictions[0][0] == "punchy"
        assert predictions[0][1] > 0.5  # High probability

    @pytest.mark.asyncio
    async def test_cache_hit_tracking(self):
        """Test that cache hits are tracked correctly"""
        manager = MultiTierBufferManager()

        # Populate caches
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        initial_hits = manager.l1_hits

        # Check cached chunk (should hit)
        is_cached, tier = manager.is_chunk_cached(1, "adaptive", 0, 1.0)
        assert is_cached is True
        assert tier == "L1"
        assert manager.l1_hits == initial_hits + 1

        # Check non-existent chunk (should miss)
        is_cached, tier = manager.is_chunk_cached(1, "adaptive", 999, 1.0)
        assert is_cached is False
        assert manager.l1_misses > 0

    @pytest.mark.asyncio
    async def test_track_change_clears_caches(self):
        """Test that changing tracks clears old caches"""
        manager = MultiTierBufferManager()

        # Populate for track 1
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        track_1_entries = len(manager.l1_cache.entries)
        assert track_1_entries > 0

        # Switch to track 2
        await manager.update_position(track_id=2, position=0.0, preset="adaptive", intensity=1.0)

        # Old track should be cleared
        track_1_still_cached = any(
            entry.track_id == 1 for entry in manager.l1_cache.entries.values()
        )
        assert not track_1_still_cached

    @pytest.mark.asyncio
    async def test_stats_api(self):
        """Test that stats API returns comprehensive data"""
        manager = MultiTierBufferManager()

        # Populate some data
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        # Trigger some hits
        manager.is_chunk_cached(1, "adaptive", 0, 1.0)
        manager.is_chunk_cached(1, "adaptive", 1, 1.0)
        manager.is_chunk_cached(1, "adaptive", 999, 1.0)  # Miss

        stats = manager.get_cache_stats()

        # Verify structure
        assert 'l1' in stats
        assert 'l2' in stats
        assert 'l3' in stats
        assert 'overall' in stats
        assert 'prediction' in stats

        # Verify metrics exist
        assert 'hit_rate' in stats['l1']
        assert 'size_mb' in stats['l1']
        assert 'count' in stats['l1']
        assert 'total_hits' in stats['overall']
        assert 'overall_hit_rate' in stats['overall']

        # Verify hit rate calculation
        assert stats['overall']['total_hits'] >= 2
        assert stats['overall']['total_misses'] >= 1


class TestPerformanceCharacteristics:
    """Tests for performance targets"""

    @pytest.mark.asyncio
    async def test_position_update_is_fast(self):
        """Test that position updates complete quickly"""
        manager = MultiTierBufferManager()

        start = time.time()
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)
        duration = time.time() - start

        # Should complete in < 100ms
        assert duration < 0.1, f"Position update took {duration*1000:.1f}ms (expected < 100ms)"

    @pytest.mark.asyncio
    async def test_cache_check_is_instant(self):
        """Test that cache checks are very fast"""
        manager = MultiTierBufferManager()

        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        # Time 100 cache checks
        start = time.time()
        for _ in range(100):
            manager.is_chunk_cached(1, "adaptive", 0, 1.0)
        duration = time.time() - start

        # Should average < 1ms per check
        avg_ms = (duration / 100) * 1000
        assert avg_ms < 1.0, f"Cache check took {avg_ms:.2f}ms (expected < 1ms)"

    @pytest.mark.asyncio
    async def test_memory_usage_within_limits(self):
        """Test that total memory stays within 99MB limit"""
        manager = MultiTierBufferManager()

        # Populate all caches to max
        for i in range(20):  # Multiple positions
            await manager.update_position(
                track_id=1,
                position=float(i * 30),  # Every 30 seconds
                preset="adaptive",
                intensity=1.0
            )

        stats = manager.get_cache_stats()
        total_mb = stats['overall']['total_size_mb']

        # Should be under 99MB limit
        assert total_mb < 99, f"Memory usage {total_mb:.1f}MB exceeds 99MB limit"


class TestErrorHandling:
    """Tests for error scenarios"""

    @pytest.mark.asyncio
    async def test_worker_handles_missing_track(self):
        """Test that worker handles missing tracks gracefully"""
        manager = MultiTierBufferManager()

        library = MockLibraryManager()
        # Override to return None
        library.tracks.get_by_id = lambda track_id: None

        worker = MultiTierBufferWorker(manager, library)

        await worker.start()
        await manager.update_position(track_id=999, position=0.0, preset="adaptive", intensity=1.0)

        # Give worker time to attempt processing
        await asyncio.sleep(0.5)

        # Should not crash, just log warning
        assert worker.running is True

        await worker.stop()

    @pytest.mark.asyncio
    async def test_cache_overflow_triggers_eviction(self):
        """Test that cache evicts entries when full"""
        from multi_tier_buffer import CacheEntry

        manager = MultiTierBufferManager()

        # Fill L1 cache to capacity
        for i in range(20):  # More entries than can fit
            entry = CacheEntry(
                track_id=1,
                preset="adaptive",
                chunk_idx=i,
                intensity=1.0,
                timestamp=time.time(),
                probability=1.0 / (i + 1)  # Decreasing probability
            )
            await manager.l1_cache.add_entry(entry)

        # Check that cache size is within limit
        assert manager.l1_cache.get_size_mb() <= manager.l1_cache.max_size_mb * 1.1  # Allow 10% tolerance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
