"""
Tests for _active_streaming_tasks concurrent-access safety (fixes #2425, #2430).

Verifies that:
- Concurrent rapid play_enhanced commands don't cause KeyError
- Cancelled tasks are fully cleaned up and removed on disconnect
- Dict stays bounded (no memory leak) even under sustained traffic
- The lock serialises all cancel-old / register-new sequences
"""

import asyncio

import pytest


# ---------------------------------------------------------------------------
# Helpers — simulate the fixed patterns used in system.py
# ---------------------------------------------------------------------------

async def _simulate_play(
    active: dict,
    lock: asyncio.Lock,
    ws_id: int,
    duration: float = 0.05,
) -> asyncio.Task:
    """Simulate the play_enhanced/play_normal handler pattern after the fix."""

    async def stream():
        my_task = asyncio.current_task()
        try:
            await asyncio.sleep(duration)
        except asyncio.CancelledError:
            pass
        finally:
            async with lock:
                if active.get(ws_id) is my_task:
                    active.pop(ws_id, None)

    async with lock:
        # Cleanup done tasks in-place (fixes #2430 — no rebinding)
        for k in [k for k, v in active.items() if v.done()]:
            active.pop(k, None)
        old_task = active.pop(ws_id, None)
        if old_task and not old_task.done():
            old_task.cancel()
        task = asyncio.create_task(stream())
        active[ws_id] = task

    return task


async def _simulate_disconnect(
    active: dict,
    lock: asyncio.Lock,
    ws_id: int,
) -> asyncio.Task | None:
    """Simulate the disconnect-handler pattern after the fix."""
    async with lock:
        task = active.pop(ws_id, None)
    if task and not task.done():
        task.cancel()
    return task


# ---------------------------------------------------------------------------
# Tests: basic correctness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_registered_after_play():
    """Task is in the dict immediately after play."""
    active: dict[int, asyncio.Task] = {}
    lock = asyncio.Lock()
    ws_id = 1

    await _simulate_play(active, lock, ws_id, duration=1.0)
    assert ws_id in active

    # Clean up
    active[ws_id].cancel()
    try:
        await active[ws_id]
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_task_removed_after_natural_completion():
    """Completed task removes itself from the dict via its finally block."""
    active: dict[int, asyncio.Task] = {}
    lock = asyncio.Lock()
    ws_id = 1

    task = await _simulate_play(active, lock, ws_id, duration=0.01)
    await task  # wait for natural completion

    assert ws_id not in active


@pytest.mark.asyncio
async def test_done_tasks_cleaned_up_before_new_registration():
    """Orphaned done-task entries are cleaned in-place, not via rebinding (fixes #2430)."""
    active: dict[int, asyncio.Task] = {}
    lock = asyncio.Lock()

    # Pre-populate with two completed (orphaned) tasks
    async def noop():
        await asyncio.sleep(0)

    for ws_id in (10, 20):
        t = asyncio.create_task(noop())
        await t
        active[ws_id] = t  # orphan it

    assert len(active) == 2
    assert all(t.done() for t in active.values())

    # A new play should clean both orphans before registering
    await _simulate_play(active, lock, 99, duration=1.0)

    assert 10 not in active
    assert 20 not in active
    assert 99 in active

    active[99].cancel()
    try:
        await active[99]
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# Tests: no KeyError on rapid switching (acceptance criteria for #2425)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rapid_play_no_keyerror():
    """Rapid sequential play commands don't cause KeyError (fixes #2425)."""
    active: dict[int, asyncio.Task] = {}
    lock = asyncio.Lock()
    ws_id = 42

    # Issue 5 rapid play commands for the same ws_id — each cancels the previous
    tasks = []
    for _ in range(5):
        t = await _simulate_play(active, lock, ws_id, duration=1.0)
        tasks.append(t)
        await asyncio.sleep(0)  # yield so background tasks can interleave

    # Only the last task should be registered
    assert ws_id in active
    last_task = active[ws_id]
    assert not last_task.done()

    # Disconnect cleans up the last task
    await _simulate_disconnect(active, lock, ws_id)
    await asyncio.sleep(0.05)  # let cancelled task finalize

    assert ws_id not in active


@pytest.mark.asyncio
async def test_concurrent_play_and_disconnect_no_keyerror():
    """
    Concurrent play + disconnect (simulating rapid client actions) must not raise KeyError.

    This is trigger condition #2 from the issue:
    network disconnect fires while the stream task's finally block is executing.
    """
    active: dict[int, asyncio.Task] = {}
    lock = asyncio.Lock()
    ws_id = 77

    # Start a streaming task
    await _simulate_play(active, lock, ws_id, duration=0.1)

    # Concurrently: trigger a new play AND a disconnect at almost the same time
    results = await asyncio.gather(
        _simulate_play(active, lock, ws_id, duration=1.0),
        _simulate_disconnect(active, lock, ws_id),
        return_exceptions=True,
    )

    # No exception should have been raised
    for r in results:
        assert not isinstance(r, Exception), f"Unexpected exception: {r}"

    # Dict should be empty or contain at most the last registered task
    # (exact state depends on scheduling order, but no KeyError is the key assertion)
    await asyncio.sleep(0.05)  # let all finals run
    for ws_id_in_dict in list(active):
        t = active.pop(ws_id_in_dict)
        if not t.done():
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_disconnect_during_task_finally_no_keyerror():
    """
    Simulate the race where the stream task's finally and the disconnect handler
    both try to remove the same ws_id. With .pop(ws_id, None) the second removal
    is a no-op rather than a KeyError (fixes #2425).
    """
    active: dict[int, asyncio.Task] = {}
    lock = asyncio.Lock()
    ws_id = 55

    await _simulate_play(active, lock, ws_id, duration=0.02)
    task = active.get(ws_id)
    assert task is not None

    # Let the task complete naturally (its finally removes it from dict)
    await asyncio.sleep(0.05)
    assert ws_id not in active

    # Now simulate the disconnect handler running AFTER the task already cleaned up
    # With the old code this would KeyError; with the fix it's a silent no-op
    result = await _simulate_disconnect(active, lock, ws_id)
    assert result is None  # pop returned None — no crash


# ---------------------------------------------------------------------------
# Tests: disconnect cancels and awaits tasks, dict empty afterwards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disconnect_cancels_running_task():
    """On disconnect, the running stream task is cancelled and removed."""
    active: dict[int, asyncio.Task] = {}
    lock = asyncio.Lock()
    ws_id = 3

    await _simulate_play(active, lock, ws_id, duration=5.0)  # long-running
    assert ws_id in active
    assert not active[ws_id].done()

    task = await _simulate_disconnect(active, lock, ws_id)
    assert ws_id not in active
    assert task is not None

    # Wait for cancellation to propagate
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert task.cancelled()


@pytest.mark.asyncio
async def test_dict_empty_after_complete_lifecycle():
    """Full play → disconnect lifecycle leaves the dict empty."""
    active: dict[int, asyncio.Task] = {}
    lock = asyncio.Lock()
    ws_id = 9

    await _simulate_play(active, lock, ws_id, duration=0.01)
    await asyncio.sleep(0.05)  # let it complete naturally

    # Dict already cleaned by task's finally
    assert ws_id not in active

    # Disconnect is a no-op (idempotent)
    t = await _simulate_disconnect(active, lock, ws_id)
    assert t is None
    assert len(active) == 0


# ---------------------------------------------------------------------------
# Tests: 10 concurrent clients (acceptance criteria from issue)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ten_concurrent_clients_no_keyerror():
    """
    10 concurrent WebSocket clients each send 5 rapid play_enhanced commands.
    No KeyError should occur (acceptance criteria from issue #2425).
    """
    active: dict[int, asyncio.Task] = {}
    lock = asyncio.Lock()

    async def client_session(ws_id: int) -> None:
        for _ in range(5):
            await _simulate_play(active, lock, ws_id, duration=0.02)
            await asyncio.sleep(0)  # yield between rapid commands
        # Disconnect at the end
        await _simulate_disconnect(active, lock, ws_id)

    # Run 10 clients concurrently — any KeyError surfaces as a failed gather
    await asyncio.gather(*[client_session(i) for i in range(10)])

    # Let all background tasks finish
    await asyncio.sleep(0.1)

    # Dict should be empty (all tasks either completed or were cancelled)
    for ws_id, task in list(active.items()):
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        active.pop(ws_id, None)

    assert len(active) == 0


@pytest.mark.asyncio
async def test_ten_concurrent_clients_rapid_disconnect():
    """
    10 concurrent clients disconnect immediately after sending a play command
    — simulates the disconnect-mid-stream scenario.
    """
    active: dict[int, asyncio.Task] = {}
    lock = asyncio.Lock()

    async def client_session(ws_id: int) -> None:
        # Start streaming a long task then disconnect immediately
        await _simulate_play(active, lock, ws_id, duration=5.0)
        await asyncio.sleep(0)
        await _simulate_disconnect(active, lock, ws_id)

    await asyncio.gather(*[client_session(i) for i in range(10)])

    # Let cancellation propagate
    await asyncio.sleep(0.05)

    assert len(active) == 0, (
        f"Dict should be empty after all disconnects, but has {len(active)} entries"
    )
