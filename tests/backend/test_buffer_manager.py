"""
Tests for Buffer Manager
~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the smart buffer management system for instant preset switching.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from buffer_manager import BufferManager, AVAILABLE_PRESETS, CHUNK_DURATION


class TestBufferManager:
    """Tests for BufferManager"""

    @pytest.fixture
    def manager(self):
        """Create buffer manager instance"""
        return BufferManager()

    def test_initialization(self, manager):
        """Test buffer manager initialization"""
        assert manager.current_track_id is None
        assert manager.current_position == 0.0
        assert manager.intensity == 1.0
        assert manager.buffered_chunks == {}
        assert manager.processing_tasks == set()
        assert hasattr(manager, '_lock')

    def test_get_current_chunk(self, manager):
        """Test chunk calculation from position"""
        # At 0 seconds -> chunk 0
        assert manager._get_current_chunk(0.0) == 0

        # At 15 seconds (middle of chunk 0)
        assert manager._get_current_chunk(15.0) == 0

        # At 29.9 seconds (end of chunk 0)
        assert manager._get_current_chunk(29.9) == 0

        # At 30 seconds -> chunk 1
        assert manager._get_current_chunk(30.0) == 1

        # At 45 seconds -> chunk 1
        assert manager._get_current_chunk(45.0) == 1

        # At 60 seconds -> chunk 2
        assert manager._get_current_chunk(60.0) == 2

    def test_get_task_key(self, manager):
        """Test task key generation"""
        key = manager._get_task_key(
            track_id=123,
            preset="adaptive",
            chunk_idx=5,
            intensity=0.8
        )

        assert isinstance(key, str)
        assert "123" in key
        assert "adaptive" in key
        assert "5" in key
        assert "0.8" in key

    def test_get_task_key_uniqueness(self, manager):
        """Test that different parameters generate different keys"""
        key1 = manager._get_task_key(1, "adaptive", 0, 1.0)
        key2 = manager._get_task_key(1, "adaptive", 1, 1.0)  # Different chunk
        key3 = manager._get_task_key(1, "gentle", 0, 1.0)    # Different preset
        key4 = manager._get_task_key(2, "adaptive", 0, 1.0)  # Different track

        assert key1 != key2
        assert key1 != key3
        assert key1 != key4

    @pytest.mark.asyncio
    async def test_update_position_basic(self, manager):
        """Test basic position update"""
        track_id = 1
        position = 15.0
        intensity = 1.0

        await manager.update_position(track_id, position, intensity)

        assert manager.current_track_id == track_id
        assert manager.current_position == position
        assert manager.intensity == intensity

    @pytest.mark.asyncio
    async def test_update_position_initializes_buffers(self, manager):
        """Test that position update initializes buffer tracking"""
        track_id = 1
        await manager.update_position(track_id, 0.0)

        # Should initialize tracking for this track
        assert track_id in manager.buffered_chunks

    @pytest.mark.asyncio
    async def test_update_position_triggers_buffering(self, manager):
        """Test that position update triggers buffering for all presets"""
        track_id = 1
        await manager.update_position(track_id, 0.0)

        # Should initialize preset tracking
        for preset in AVAILABLE_PRESETS:
            assert preset in manager.buffered_chunks[track_id]
            assert isinstance(manager.buffered_chunks[track_id][preset], set)

    @pytest.mark.asyncio
    async def test_update_position_clears_old_tracks(self, manager):
        """Test that changing tracks clears old buffer data"""
        # Buffer for track 1
        await manager.update_position(track_id=1, position=0.0)
        assert 1 in manager.buffered_chunks

        # Switch to track 2
        await manager.update_position(track_id=2, position=0.0)

        # Old track should be cleared
        assert 1 not in manager.buffered_chunks
        assert 2 in manager.buffered_chunks

    @pytest.mark.asyncio
    async def test_update_position_multiple_updates_same_track(self, manager):
        """Test multiple position updates for same track"""
        track_id = 1

        # Update to position 15s (chunk 0)
        await manager.update_position(track_id, 15.0)
        assert manager.current_position == 15.0

        # Update to position 45s (chunk 1)
        await manager.update_position(track_id, 45.0)
        assert manager.current_position == 45.0
        assert manager.current_track_id == track_id

        # Track data should still be present
        assert track_id in manager.buffered_chunks

    def test_mark_chunk_ready(self, manager):
        """Test marking chunks as ready"""
        track_id = 1
        preset = "adaptive"
        chunk_idx = 0
        intensity = 1.0

        manager.mark_chunk_ready(track_id, preset, chunk_idx, intensity)

        # Chunk should be marked as buffered
        assert track_id in manager.buffered_chunks
        assert preset in manager.buffered_chunks[track_id]
        assert chunk_idx in manager.buffered_chunks[track_id][preset]

    def test_mark_chunk_ready_multiple_chunks(self, manager):
        """Test marking multiple chunks as ready"""
        track_id = 1
        preset = "adaptive"

        manager.mark_chunk_ready(track_id, preset, 0, 1.0)
        manager.mark_chunk_ready(track_id, preset, 1, 1.0)
        manager.mark_chunk_ready(track_id, preset, 2, 1.0)

        # All chunks should be marked
        buffered = manager.buffered_chunks[track_id][preset]
        assert 0 in buffered
        assert 1 in buffered
        assert 2 in buffered
        assert len(buffered) == 3

    def test_mark_chunk_ready_multiple_presets(self, manager):
        """Test marking chunks across different presets"""
        track_id = 1

        manager.mark_chunk_ready(track_id, "adaptive", 0, 1.0)
        manager.mark_chunk_ready(track_id, "gentle", 0, 1.0)
        manager.mark_chunk_ready(track_id, "warm", 0, 1.0)

        # Each preset should have the chunk buffered
        assert 0 in manager.buffered_chunks[track_id]["adaptive"]
        assert 0 in manager.buffered_chunks[track_id]["gentle"]
        assert 0 in manager.buffered_chunks[track_id]["warm"]

    @pytest.mark.asyncio
    async def test_ensure_buffers_tracks_needed_chunks(self, manager):
        """Test that _ensure_buffers identifies chunks needing buffering"""
        track_id = 1
        current_chunk = 0
        next_chunk = 1
        intensity = 1.0

        # Initialize
        manager.buffered_chunks[track_id] = {}

        await manager._ensure_buffers(track_id, current_chunk, next_chunk, intensity)

        # Should have initialized presets
        for preset in AVAILABLE_PRESETS:
            assert preset in manager.buffered_chunks[track_id]

    @pytest.mark.asyncio
    async def test_concurrent_position_updates(self, manager):
        """Test thread-safe concurrent position updates"""
        track_id = 1

        # Simulate multiple concurrent updates
        tasks = [
            manager.update_position(track_id, float(i * 10))
            for i in range(10)
        ]

        # Should complete without deadlock
        await asyncio.gather(*tasks)

        # Final state should be consistent
        assert manager.current_track_id == track_id
        assert track_id in manager.buffered_chunks

    def test_available_presets_constant(self):
        """Test that AVAILABLE_PRESETS constant is defined correctly"""
        assert isinstance(AVAILABLE_PRESETS, list)
        assert len(AVAILABLE_PRESETS) > 0
        assert "adaptive" in AVAILABLE_PRESETS
        assert "gentle" in AVAILABLE_PRESETS

    def test_chunk_duration_constant(self):
        """Test that CHUNK_DURATION constant is defined"""
        assert isinstance(CHUNK_DURATION, int)
        assert CHUNK_DURATION > 0
        assert CHUNK_DURATION == 30  # 30 seconds per chunk


class TestBufferManagerEdgeCases:
    """Edge case tests for BufferManager"""

    @pytest.fixture
    def manager(self):
        """Create buffer manager instance"""
        return BufferManager()

    @pytest.mark.asyncio
    async def test_update_position_zero_position(self, manager):
        """Test update at position 0"""
        await manager.update_position(track_id=1, position=0.0)
        assert manager.current_position == 0.0
        assert manager._get_current_chunk(0.0) == 0

    @pytest.mark.asyncio
    async def test_update_position_large_position(self, manager):
        """Test update at large position (many chunks in)"""
        position = 3600.0  # 1 hour in
        await manager.update_position(track_id=1, position=position)

        assert manager.current_position == position
        expected_chunk = int(3600 // 30)  # 120 chunks in
        assert manager._get_current_chunk(position) == expected_chunk

    @pytest.mark.asyncio
    async def test_update_position_fractional_intensity(self, manager):
        """Test update with fractional intensity"""
        await manager.update_position(track_id=1, position=0.0, intensity=0.5)
        assert manager.intensity == 0.5

        await manager.update_position(track_id=1, position=0.0, intensity=0.0)
        assert manager.intensity == 0.0

    def test_mark_chunk_ready_idempotent(self, manager):
        """Test that marking same chunk multiple times is safe"""
        track_id = 1
        preset = "adaptive"
        chunk_idx = 0

        manager.mark_chunk_ready(track_id, preset, chunk_idx, 1.0)
        manager.mark_chunk_ready(track_id, preset, chunk_idx, 1.0)
        manager.mark_chunk_ready(track_id, preset, chunk_idx, 1.0)

        # Should only be in set once
        buffered = manager.buffered_chunks[track_id][preset]
        assert chunk_idx in buffered
        assert len(buffered) == 1

    @pytest.mark.asyncio
    async def test_rapid_track_switching(self, manager):
        """Test rapid switching between tracks"""
        for track_id in range(1, 11):
            await manager.update_position(track_id=track_id, position=0.0)

        # Only last track should be buffered
        assert manager.current_track_id == 10
        assert 10 in manager.buffered_chunks
        # Earlier tracks should be cleared
        for track_id in range(1, 10):
            assert track_id not in manager.buffered_chunks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
