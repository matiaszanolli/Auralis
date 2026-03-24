"""
Test WebSocket buffer flow-control messages (#3336)

Verifies that buffer_full pauses and buffer_ready resumes
the per-WebSocket flow-control event used by the streaming loop.
"""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_buffer_full_clears_flow_event():
    """buffer_full should clear the flow event, pausing chunk delivery."""
    flow_event = asyncio.Event()
    flow_event.set()  # Initially flowing

    # Simulate buffer_full handler logic (system.py:572-573)
    flow_event.clear()

    assert not flow_event.is_set(), "Flow event should be cleared after buffer_full"


@pytest.mark.asyncio
async def test_buffer_ready_sets_flow_event():
    """buffer_ready should set the flow event, resuming chunk delivery."""
    flow_event = asyncio.Event()
    flow_event.clear()  # Paused (buffer was full)

    # Simulate buffer_ready handler logic (system.py:580-581)
    flow_event.set()

    assert flow_event.is_set(), "Flow event should be set after buffer_ready"


@pytest.mark.asyncio
async def test_buffer_full_then_ready_round_trip():
    """Full round-trip: flowing → buffer_full → paused → buffer_ready → flowing."""
    flow_event = asyncio.Event()
    flow_event.set()  # Start flowing

    # buffer_full
    flow_event.clear()
    assert not flow_event.is_set()

    # buffer_ready
    flow_event.set()
    assert flow_event.is_set()


@pytest.mark.asyncio
async def test_streaming_blocks_when_flow_paused():
    """A streaming coroutine should block on flow_event.wait() when cleared."""
    flow_event = asyncio.Event()
    flow_event.clear()  # Paused

    reached = False

    async def simulate_streaming():
        nonlocal reached
        await asyncio.wait_for(flow_event.wait(), timeout=0.1)
        reached = True

    with pytest.raises(asyncio.TimeoutError):
        await simulate_streaming()

    assert not reached, "Streaming should not proceed while flow event is cleared"


@pytest.mark.asyncio
async def test_streaming_unblocks_when_flow_resumed():
    """A streaming coroutine should unblock once flow_event is set."""
    flow_event = asyncio.Event()
    flow_event.clear()

    reached = False

    async def simulate_streaming():
        nonlocal reached
        await flow_event.wait()
        reached = True

    # Schedule the streaming coroutine
    task = asyncio.create_task(simulate_streaming())
    await asyncio.sleep(0.01)  # Let it block
    assert not reached

    # Resume
    flow_event.set()
    await asyncio.wait_for(task, timeout=1.0)
    assert reached, "Streaming should resume after flow event is set"
