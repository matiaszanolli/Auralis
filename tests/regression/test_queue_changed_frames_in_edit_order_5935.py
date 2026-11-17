"""queue_changed frames leave in edit order (#5935).

Each mutator left its engine lock before reading, hydrating and sending, so a
second edit could finish hydrating first: its frame went out, then the first
edit's slower frame overwrote it on the client with the older queue. The
read-hydrate-send now runs under one process-wide lock, so the last frame sent
always describes the latest engine queue.
"""

import asyncio

import pytest

from tests.regression.test_queue_edits_update_player_state_5460 import _engine_ids, _service


def _sent_queue_ids(ws) -> list[list[int]]:
    return [
        [t["id"] for t in c.args[0]["data"]["tracks"]]
        for c in ws.broadcast.call_args_list
        if c.args[0].get("type") == "queue_changed"
    ]


@pytest.mark.regression
@pytest.mark.asyncio
async def test_a_slow_first_broadcast_cannot_overwrite_a_later_edit():
    service, controller, _, ws = await _service()
    real_resolve = service._enricher.resolve_tracks
    in_hydrate, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def slow_first(paths):
        nonlocal calls
        calls += 1
        if calls == 1:
            in_hydrate.set()
            await release.wait()
        return await real_resolve(paths)

    service._enricher.resolve_tracks = slow_first
    ws.broadcast.reset_mock()

    first = asyncio.create_task(service._broadcast_queue_changed("removed"))
    await in_hydrate.wait()  # edit A has read the 4-track queue and is hydrating
    controller.remove_track(3)  # edit B lands in the engine meanwhile
    second = asyncio.create_task(service._broadcast_queue_changed("removed"))
    for _ in range(5):
        await asyncio.sleep(0)
    release.set()
    await asyncio.gather(first, second)

    sent = _sent_queue_ids(ws)
    assert sent[-1] == _engine_ids(controller) == [1, 2, 3]
    assert sent == [[1, 2, 3, 4], [1, 2, 3]]
