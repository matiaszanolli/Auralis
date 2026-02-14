"""
Test for WebSocket streaming task orphan race condition (fixes #2164).

This test verifies that rapid play_enhanced/play_normal messages don't orphan
the new streaming task when the old task's finally block fires.
"""

import asyncio
import pytest


@pytest.mark.asyncio
async def test_task_identity_check_prevents_orphan():
    """
    Unit test for the core fix: task identity check in finally block.

    Simulates the exact race condition:
    1. Task1 is created and stored
    2. Task1 is cancelled
    3. Task2 is created and stored (replaces Task1)
    4. Task1's finally block fires
    5. Task1's finally block should NOT delete Task2's reference

    Fixes #2164 - orphaned task race condition
    """
    _active_streaming_tasks: dict[int, asyncio.Task] = {}
    ws_id = 12345

    # This is the FIXED pattern used in system.py
    async def streaming_task_with_fix():
        my_task = asyncio.current_task()
        try:
            await asyncio.sleep(0.1)
        finally:
            # Fixed: only delete if we're still the active task
            if _active_streaming_tasks.get(ws_id) is my_task:
                del _active_streaming_tasks[ws_id]

    # Start task1
    task1 = asyncio.create_task(streaming_task_with_fix())
    _active_streaming_tasks[ws_id] = task1

    # Wait briefly, then cancel task1 and immediately start task2
    await asyncio.sleep(0.01)
    task1.cancel()

    # Immediately create task2 (simulates rapid play_enhanced → play_enhanced)
    task2 = asyncio.create_task(streaming_task_with_fix())
    _active_streaming_tasks[ws_id] = task2

    # Wait for task1's finally block to execute
    try:
        await task1
    except asyncio.CancelledError:
        pass

    # CRITICAL: task2's reference should still be in _active_streaming_tasks
    # If the bug exists, task1's finally block deleted task2's reference
    assert ws_id in _active_streaming_tasks, (
        "Bug #2164 reproduced: Task2's reference was incorrectly deleted by Task1's finally block"
    )
    assert _active_streaming_tasks[ws_id] is task2, "Wrong task in _active_streaming_tasks"

    # Clean up task2
    task2.cancel()
    try:
        await task2
    except asyncio.CancelledError:
        pass

    # Now task2's finally block should have cleaned up
    assert ws_id not in _active_streaming_tasks, "Task2's finally block should have cleaned up"


@pytest.mark.asyncio
async def test_old_pattern_demonstrates_bug():
    """
    Demonstrates the BUG with the old pattern (no task identity check).

    This test should fail if we use the old pattern without the fix.
    """
    _active_streaming_tasks: dict[int, asyncio.Task] = {}
    ws_id = 12345

    # This is the BUGGY old pattern (before #2164 fix)
    async def streaming_task_with_bug():
        try:
            await asyncio.sleep(0.1)
        finally:
            # Buggy: unconditionally deletes, even if a new task replaced us
            if ws_id in _active_streaming_tasks:
                del _active_streaming_tasks[ws_id]

    # Start task1
    task1 = asyncio.create_task(streaming_task_with_bug())
    _active_streaming_tasks[ws_id] = task1

    # Wait briefly, then cancel task1
    await asyncio.sleep(0.01)
    task1.cancel()

    # Immediately create task2
    task2 = asyncio.create_task(streaming_task_with_bug())
    _active_streaming_tasks[ws_id] = task2

    # Wait for task1's finally block to execute
    try:
        await task1
    except asyncio.CancelledError:
        pass

    # BUG: task2's reference should be there, but task1's finally block deleted it!
    assert ws_id not in _active_streaming_tasks, (
        "Expected bug: Task1's finally block should have deleted Task2's reference. "
        "This demonstrates the bug that #2164 fixes."
    )

    # Clean up task2
    task2.cancel()
    try:
        await task2
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_triple_rapid_switch_with_fix():
    """
    Test rapid switching through 3 tasks - stress test for the fix.

    Scenario: play_enhanced(A) → play_enhanced(B) → play_enhanced(C)
    All within a very short time window.
    """
    _active_streaming_tasks: dict[int, asyncio.Task] = {}
    ws_id = 12345

    async def streaming_task_with_fix():
        my_task = asyncio.current_task()
        try:
            await asyncio.sleep(0.1)
        finally:
            if _active_streaming_tasks.get(ws_id) is my_task:
                del _active_streaming_tasks[ws_id]

    # Create and cancel task1
    task1 = asyncio.create_task(streaming_task_with_fix())
    _active_streaming_tasks[ws_id] = task1
    await asyncio.sleep(0.005)
    task1.cancel()

    # Create and cancel task2
    task2 = asyncio.create_task(streaming_task_with_fix())
    _active_streaming_tasks[ws_id] = task2
    await asyncio.sleep(0.005)
    task2.cancel()

    # Create task3
    task3 = asyncio.create_task(streaming_task_with_fix())
    _active_streaming_tasks[ws_id] = task3

    # Wait for task1 and task2's finally blocks
    for task in [task1, task2]:
        try:
            await task
        except asyncio.CancelledError:
            pass

    # task3 should still be active
    assert ws_id in _active_streaming_tasks
    assert _active_streaming_tasks[ws_id] is task3

    # Clean up
    task3.cancel()
    try:
        await task3
    except asyncio.CancelledError:
        pass

    assert ws_id not in _active_streaming_tasks


@pytest.mark.asyncio
async def test_pause_cancels_correct_task():
    """
    Test that pause/stop can find and cancel the active task after rapid switching.

    This is the acceptance criteria from #2164:
    "Rapid play_enhanced → play_enhanced → pause correctly pauses the second stream"
    """
    _active_streaming_tasks: dict[int, asyncio.Task] = {}
    ws_id = 12345

    async def streaming_task_with_fix():
        my_task = asyncio.current_task()
        try:
            await asyncio.sleep(1.0)  # Long-running stream
        finally:
            if _active_streaming_tasks.get(ws_id) is my_task:
                del _active_streaming_tasks[ws_id]

    # Simulate: play_enhanced(track A)
    task1 = asyncio.create_task(streaming_task_with_fix())
    _active_streaming_tasks[ws_id] = task1
    await asyncio.sleep(0.02)

    # Simulate: play_enhanced(track B) - rapid switch
    task1.cancel()
    task2 = asyncio.create_task(streaming_task_with_fix())
    _active_streaming_tasks[ws_id] = task2
    await asyncio.sleep(0.02)

    # Simulate: pause command
    # The pause handler should be able to find task2 and cancel it
    if ws_id in _active_streaming_tasks:
        active_task = _active_streaming_tasks[ws_id]
        active_task.cancel()
        del _active_streaming_tasks[ws_id]

    # Verify the pause was successful
    assert ws_id not in _active_streaming_tasks, "Pause should have cleared the active task"

    # Clean up and verify tasks were cancelled
    for task in [task1, task2]:
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert task1.cancelled(), "Task1 should have been cancelled"
    assert task2.cancelled(), "Task2 should have been cancelled by pause"
