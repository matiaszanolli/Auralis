"""
Tests for Buffer Worker
~~~~~~~~~~~~~~~~~~~~~~~~

Tests the background worker for predictive chunk processing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from buffer_worker import BufferWorker


class TestBufferWorker:
    """Tests for BufferWorker"""

    @pytest.fixture
    def mock_buffer_manager(self):
        """Create mock buffer manager"""
        manager = Mock()
        manager.current_track_id = None
        manager.intensity = 1.0
        manager.get_needed_chunks = Mock(return_value={})
        return manager

    @pytest.fixture
    def mock_library_manager(self):
        """Create mock library manager"""
        manager = Mock()
        manager.tracks = Mock()
        manager.tracks.get_by_id = Mock(return_value=None)
        return manager

    @pytest.fixture
    def worker(self, mock_buffer_manager, mock_library_manager):
        """Create buffer worker instance"""
        return BufferWorker(mock_buffer_manager, mock_library_manager)

    def test_initialization(self, worker, mock_buffer_manager, mock_library_manager):
        """Test buffer worker initialization"""
        assert worker.buffer_manager is mock_buffer_manager
        assert worker.library_manager is mock_library_manager
        assert worker.running is False
        assert worker._worker_task is None

    @pytest.mark.asyncio
    async def test_start(self, worker):
        """Test starting the worker"""
        await worker.start()

        assert worker.running is True
        assert worker._worker_task is not None

        # Clean up
        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop(self, worker):
        """Test stopping the worker"""
        await worker.start()
        assert worker.running is True

        await worker.stop()

        assert worker.running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self, worker):
        """Test that starting multiple times doesn't create multiple tasks"""
        await worker.start()
        first_task = worker._worker_task

        await worker.start()  # Start again
        second_task = worker._worker_task

        # Should be the same task
        assert first_task is second_task

        # Clean up
        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, worker):
        """Test that stopping when not running is safe"""
        # Should not raise
        await worker.stop()
        assert worker.running is False

    @pytest.mark.asyncio
    async def test_process_needed_chunks_no_track(self, worker):
        """Test processing when no track is playing"""
        worker.buffer_manager.current_track_id = None

        # Should return early without error
        await worker._process_needed_chunks()

        # get_needed_chunks should not be called
        worker.buffer_manager.get_needed_chunks.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_needed_chunks_no_chunks_needed(self, worker):
        """Test processing when no chunks need buffering"""
        worker.buffer_manager.current_track_id = 1
        worker.buffer_manager.get_needed_chunks.return_value = {}

        await worker._process_needed_chunks()

        # Should call get_needed_chunks but not try to get track
        worker.buffer_manager.get_needed_chunks.assert_called_once()
        worker.library_manager.tracks.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_needed_chunks_track_not_found(self, worker):
        """Test processing when track is not in library"""
        worker.buffer_manager.current_track_id = 1
        worker.buffer_manager.get_needed_chunks.return_value = {
            "adaptive": [0, 1]
        }
        worker.library_manager.tracks.get_by_id.return_value = None

        # Should handle gracefully without error
        await worker._process_needed_chunks()

        worker.library_manager.tracks.get_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_worker_loop_stops_when_running_false(self, worker):
        """Test that worker loop stops when running is set to False"""
        await worker.start()

        # Let it run briefly
        await asyncio.sleep(0.1)

        # Stop it
        worker.running = False

        # Wait for task to complete
        try:
            await asyncio.wait_for(worker._worker_task, timeout=2.0)
        except asyncio.CancelledError:
            pass  # Expected

        # Task should complete
        assert worker._worker_task.done() or worker._worker_task.cancelled()

    @pytest.mark.asyncio
    async def test_worker_loop_handles_exceptions(self, worker):
        """Test that worker loop continues after exceptions"""
        worker.buffer_manager.current_track_id = 1
        worker.buffer_manager.get_needed_chunks.side_effect = Exception("Test error")

        await worker.start()

        # Let it run and handle exception
        await asyncio.sleep(0.1)

        # Worker should still be running
        assert worker.running is True

        # Clean up
        await worker.stop()

    @pytest.mark.asyncio
    async def test_start_stop_cycle(self, worker):
        """Test starting and stopping multiple times"""
        # Start and stop 3 times
        for _ in range(3):
            await worker.start()
            assert worker.running is True

            await worker.stop()
            assert worker.running is False

    @pytest.mark.asyncio
    async def test_concurrent_start_stop(self, worker):
        """Test concurrent start/stop calls"""
        # Start multiple times concurrently
        await asyncio.gather(
            worker.start(),
            worker.start(),
            worker.start()
        )

        assert worker.running is True

        # Stop multiple times concurrently
        await asyncio.gather(
            worker.stop(),
            worker.stop(),
            worker.stop()
        )

        assert worker.running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
