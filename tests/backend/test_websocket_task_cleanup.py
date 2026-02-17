"""
Test WebSocket streaming task cleanup (fixes #2321)

Verifies that completed tasks are cleaned up from _active_streaming_tasks
to prevent memory leaks under sustained WebSocket traffic.
"""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_completed_tasks_are_cleaned_up():
    """
    Test that completed tasks are removed from _active_streaming_tasks
    when new tasks are created.

    Simulates the exact memory leak scenario:
    1. Task1 completes but remains in dict (orphaned)
    2. Task2 is created
    3. Cleanup should remove Task1 before adding Task2

    Acceptance criteria:
    - Completed task entries are cleaned up before adding new tasks
    - No memory leak after multiple connect/disconnect cycles
    - Active tasks are not affected by cleanup

    Fixes #2321 - _active_streaming_tasks dict memory leak
    """
    _active_streaming_tasks: dict[int, asyncio.Task] = {}

    # This is the FIXED pattern used in system.py
    async def create_streaming_task(ws_id: int):
        """Simulates the pattern used in system.py play_enhanced handler"""
        # Clean up completed tasks before adding new one (THE FIX)
        nonlocal _active_streaming_tasks
        _active_streaming_tasks = {k: v for k, v in _active_streaming_tasks.items() if not v.done()}

        # Cancel any existing streaming task for this websocket
        if ws_id in _active_streaming_tasks:
            old_task = _active_streaming_tasks[ws_id]
            if not old_task.done():
                old_task.cancel()

        # Define streaming coroutine
        async def stream_audio():
            my_task = asyncio.current_task()
            try:
                await asyncio.sleep(0.05)  # Simulate short streaming
            finally:
                # Only delete our own task reference
                if _active_streaming_tasks.get(ws_id) is my_task:
                    del _active_streaming_tasks[ws_id]

        # Start streaming in background task
        task = asyncio.create_task(stream_audio())
        _active_streaming_tasks[ws_id] = task
        return task

    # Simulate multiple WebSocket connections
    ws1_id = 1
    ws2_id = 2
    ws3_id = 3

    # Create and complete task1
    task1 = await create_streaming_task(ws1_id)
    await task1  # Wait for completion
    # After completion, task1's finally block removed it from dict
    assert ws1_id not in _active_streaming_tasks

    # Manually add completed task back to dict to simulate orphaned entry
    # (this simulates the memory leak scenario)
    _active_streaming_tasks[ws1_id] = task1
    assert ws1_id in _active_streaming_tasks
    assert task1.done()

    # Create task2 for different websocket
    task2 = await create_streaming_task(ws2_id)
    await task2

    # The cleanup should have removed task1 (completed) before adding task2
    assert ws1_id not in _active_streaming_tasks, "Completed task1 should be cleaned up"
    assert ws2_id not in _active_streaming_tasks  # task2 completed and cleaned up itself

    # Add multiple completed tasks to simulate buildup
    _active_streaming_tasks[ws1_id] = task1  # completed
    _active_streaming_tasks[ws2_id] = task2  # completed
    assert len(_active_streaming_tasks) == 2

    # Create new task for ws3 - should clean up both completed tasks
    task3 = await create_streaming_task(ws3_id)

    # Only ws3 should remain (ws1 and ws2 were cleaned up)
    assert ws1_id not in _active_streaming_tasks
    assert ws2_id not in _active_streaming_tasks
    assert ws3_id in _active_streaming_tasks
    assert len(_active_streaming_tasks) == 1

    # Clean up task3
    await task3
    assert ws3_id not in _active_streaming_tasks


@pytest.mark.asyncio
async def test_active_tasks_not_affected_by_cleanup():
    """
    Test that active (non-completed) tasks are not removed during cleanup.

    Acceptance criteria:
    - Active tasks remain in _active_streaming_tasks
    - Only completed tasks are removed
    """
    _active_streaming_tasks: dict[int, asyncio.Task] = {}

    def create_long_running_task(ws_id: int, duration: float = 1.0):
        """Creates a long-running task"""
        # Clean up completed tasks before adding new one
        nonlocal _active_streaming_tasks
        _active_streaming_tasks = {k: v for k, v in _active_streaming_tasks.items() if not v.done()}

        async def stream_audio():
            my_task = asyncio.current_task()
            try:
                await asyncio.sleep(duration)
            finally:
                if _active_streaming_tasks.get(ws_id) is my_task:
                    del _active_streaming_tasks[ws_id]

        task = asyncio.create_task(stream_audio())
        _active_streaming_tasks[ws_id] = task
        return task

    ws1_id = 1
    ws2_id = 2
    ws3_id = 3

    # Create long-running task1
    task1 = create_long_running_task(ws1_id, duration=0.5)
    await asyncio.sleep(0.01)  # Let it start

    # Verify task1 is active
    assert ws1_id in _active_streaming_tasks
    assert not _active_streaming_tasks[ws1_id].done()

    # Create and complete task2 (different websocket)
    task2 = create_long_running_task(ws2_id, duration=0.01)
    await task2  # Complete it
    assert ws2_id not in _active_streaming_tasks

    # Add completed task2 back to simulate orphaned entry
    _active_streaming_tasks[ws2_id] = task2
    assert task2.done()

    # Create task3 - should clean up task2 but NOT task1 (still active)
    task3 = create_long_running_task(ws3_id, duration=0.01)
    await asyncio.sleep(0.01)

    # task1 should still be present (active)
    # task2 should be removed (completed)
    # task3 should be present (active)
    assert ws1_id in _active_streaming_tasks, "Active task1 should not be removed by cleanup"
    assert ws2_id not in _active_streaming_tasks, "Completed task2 should be removed by cleanup"
    assert ws3_id in _active_streaming_tasks

    # Clean up remaining tasks
    for task in list(_active_streaming_tasks.values()):
        task.cancel()
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_no_leak_after_many_connections():
    """
    Test that dict doesn't grow indefinitely with many connection cycles.

    Acceptance criteria:
    - No memory leak after 100 connect/disconnect cycles
    - Dict size remains bounded (should be 0 or 1 after cleanup)
    """
    _active_streaming_tasks: dict[int, asyncio.Task] = {}

    async def simulate_connection(ws_id: int):
        """Simulates a complete WebSocket connection lifecycle"""
        # Clean up completed tasks
        nonlocal _active_streaming_tasks
        _active_streaming_tasks = {k: v for k, v in _active_streaming_tasks.items() if not v.done()}

        async def stream_audio():
            my_task = asyncio.current_task()
            try:
                await asyncio.sleep(0.001)  # Very short streaming
            finally:
                if _active_streaming_tasks.get(ws_id) is my_task:
                    del _active_streaming_tasks[ws_id]

        task = asyncio.create_task(stream_audio())
        _active_streaming_tasks[ws_id] = task
        await task  # Wait for completion

    # Simulate 100 connections
    for i in range(100):
        await simulate_connection(i)

    # Dict should be empty after all connections complete
    assert len(_active_streaming_tasks) == 0, \
        f"Dict should be empty, but has {len(_active_streaming_tasks)} entries"

    # Simulate the worst case: all tasks orphaned before cleanup
    tasks = []
    for i in range(50):
        async def dummy_task():
            await asyncio.sleep(0.001)
        task = asyncio.create_task(dummy_task())
        await task
        _active_streaming_tasks[i] = task  # Orphaned completed tasks
        tasks.append(task)

    # Verify orphaned tasks exist
    assert len(_active_streaming_tasks) == 50
    assert all(t.done() for t in _active_streaming_tasks.values())

    # Create one new connection - should clean up all 50 orphaned tasks
    await simulate_connection(999)

    # Dict should be empty now
    assert len(_active_streaming_tasks) == 0, \
        f"Cleanup failed: dict has {len(_active_streaming_tasks)} entries after cleanup"
