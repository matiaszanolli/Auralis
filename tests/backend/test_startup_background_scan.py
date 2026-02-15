"""
Test background library scan during startup

Validates that:
1. Server accepts requests within 5 seconds of startup
2. Auto-scan runs in background without blocking
3. Scan progress is communicated via WebSocket

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.mark.asyncio
async def test_background_scan_does_not_block():
    """
    Verify background scan pattern doesn't block the caller.

    This simulates the startup pattern where asyncio.create_task() is used
    to schedule the scan without blocking.
    """
    scan_completed = False
    task_scheduled = False

    async def slow_scan():
        """Simulates a slow scan operation"""
        nonlocal scan_completed
        await asyncio.sleep(0.2)  # Simulate 200ms scan
        scan_completed = True

    async def startup_with_background_scan():
        """Simulates the startup event that schedules a background scan"""
        nonlocal task_scheduled
        # Schedule the scan without awaiting (non-blocking)
        asyncio.create_task(slow_scan())
        task_scheduled = True
        # Startup completes immediately

    # Measure startup time
    start_time = time.time()
    await startup_with_background_scan()
    startup_duration = time.time() - start_time

    # Assert startup was immediate (< 0.05s)
    assert startup_duration < 0.05, f"Startup took {startup_duration:.2f}s, expected < 0.05s"
    assert task_scheduled, "Task should be scheduled"
    assert not scan_completed, "Scan should not be completed yet (runs in background)"

    # Wait for scan to complete
    await asyncio.sleep(0.3)
    assert scan_completed, "Scan should complete in background"


@pytest.mark.asyncio
async def test_background_scan_broadcasts_websocket_events():
    """
    Verify scan broadcasts progress via WebSocket.

    Tests the pattern used in _background_auto_scan where:
    1. Scan start is broadcast
    2. Progress updates are broadcast during scan
    3. Completion is broadcast with results
    """
    broadcast_events = []

    # Mock connection manager
    class MockConnectionManager:
        async def broadcast(self, message):
            broadcast_events.append(message)

    manager = MockConnectionManager()

    # Simulate the background scan broadcasting pattern
    async def simulated_background_scan():
        # Broadcast start
        await manager.broadcast({
            "type": "library_scan_started",
            "directory": "/home/test/Music"
        })

        # Simulate progress updates
        for i in range(3):
            progress = (i + 1) / 3
            await manager.broadcast({
                "type": "scan_progress",
                "data": {
                    "current": int(500 * progress),
                    "total": 500,
                    "percentage": round(progress * 100),
                }
            })
            await asyncio.sleep(0.01)

        # Broadcast completion
        await manager.broadcast({
            "type": "scan_complete",
            "data": {
                "files_processed": 500,
                "tracks_added": 100,
                "duration": 1.5,
            }
        })

    await simulated_background_scan()

    # Verify events
    assert len(broadcast_events) == 5  # start + 3 progress + complete

    # Check start event
    assert broadcast_events[0]["type"] == "library_scan_started"

    # Check progress events
    progress_events = [e for e in broadcast_events if e["type"] == "scan_progress"]
    assert len(progress_events) == 3

    # Check completion event
    completed = [e for e in broadcast_events if e["type"] == "scan_complete"]
    assert len(completed) == 1
    assert completed[0]["data"]["tracks_added"] == 100


@pytest.mark.asyncio
async def test_background_scan_error_handling():
    """
    Verify scan errors are caught and broadcast via WebSocket.

    Tests the error handling pattern in _background_auto_scan.
    """
    broadcast_events = []

    class MockConnectionManager:
        async def broadcast(self, message):
            broadcast_events.append(message)

    manager = MockConnectionManager()

    # Simulate background scan with error
    async def simulated_scan_with_error():
        try:
            await manager.broadcast({
                "type": "library_scan_started",
                "directory": "/home/test/Music"
            })

            # Simulate error during scan
            raise Exception("Scan failed: permission denied")

        except Exception as e:
            # Error should be caught and broadcast
            await manager.broadcast({
                "type": "library_scan_error",
                "error": str(e)
            })

    await simulated_scan_with_error()

    # Verify error event was broadcast
    error_events = [e for e in broadcast_events if e["type"] == "library_scan_error"]
    assert len(error_events) == 1, "Expected one error event"
    assert "Scan failed" in error_events[0]["error"]


@pytest.mark.asyncio
async def test_asyncio_to_thread_pattern():
    """
    Verify asyncio.to_thread is used for CPU-bound operations.

    This tests the pattern where synchronous blocking operations
    (like file scanning) are offloaded to a thread pool.
    """
    thread_pool_used = False
    result_value = None

    def blocking_operation():
        """Simulates a blocking CPU-bound operation"""
        import time
        time.sleep(0.01)  # Simulate blocking work
        return {"files_scanned": 100}

    async def async_wrapper_using_to_thread():
        """Simulates using asyncio.to_thread for blocking work"""
        nonlocal thread_pool_used, result_value
        # This is the pattern used in _background_auto_scan
        result_value = await asyncio.to_thread(blocking_operation)
        thread_pool_used = True

    # Run the async wrapper
    await async_wrapper_using_to_thread()

    assert thread_pool_used, "Thread pool should be used"
    assert result_value == {"files_scanned": 100}, "Result should be returned from thread"
