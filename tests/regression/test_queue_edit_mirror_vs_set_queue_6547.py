"""A queue edit's state mirror never overwrites a newer set_queue (#6547).

After its engine mutation an edit reads and hydrates the engine queue, then
mirrors it into PlayerStateManager (#5460). That mirror ignored the set_queue
generation protocol, so a set_queue that ran to completion while the edit was
still hydrating had its state overwritten by the edit's pre-set_queue queue:
every later player_state then described a queue the engine no longer played.
The mirror now runs under the sequencer's state lock and only when no newer
generation committed since the edit claimed its own, and the edit's queue_changed
frame then carries no tracks or index, so a client keeps the newer queue.
"""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from tests.regression.test_queue_edits_update_player_state_5460 import _service, _state_ids


def _engine_paths(controller):
    """set_queue stores bare filepaths in the engine, edits store track dicts."""
    return [t if isinstance(t, str) else t["filepath"] for t in controller.get_queue()]


def _state_paths(state):
    return [t.filepath for t in state.get_state().queue]


@pytest.mark.regression
@pytest.mark.asyncio
async def test_an_edit_hydrating_across_a_set_queue_leaves_the_newer_queue(monkeypatch):
    edit, controller, state, edit_ws = await _service()
    newer_service = (await _service())[0]  # a second request's service, over the same engine and state
    newer_service.player_state_manager = state
    newer_service.audio_player = SimpleNamespace(
        queue=controller, load_file=lambda _path: True, stop=lambda: None, play=lambda: None
    )

    hydrating, release = asyncio.Event(), asyncio.Event()
    real_resolve = edit._enricher.resolve_tracks

    async def slow_resolve(raw):
        resolved = await real_resolve(raw)
        hydrating.set()
        await release.wait()
        return resolved

    monkeypatch.setattr(edit._enricher, "resolve_tracks", slow_resolve)

    adding = asyncio.create_task(edit.add_track_to_queue(9))
    await asyncio.wait_for(hydrating.wait(), 5)
    await newer_service.set_queue([2, 3], start_index=0)  # completes while the edit hydrates
    release.set()
    await asyncio.wait_for(adding, 5)

    expected = ["/music/track_2.flac", "/music/track_3.flac"]
    assert _engine_paths(controller) == expected
    assert _state_paths(state) == expected, "the edit's stale mirror overwrote the newer set_queue"
    # Its frame is still sent, without the stale queue a client would apply over the newer one.
    frames = [c.args[0]["data"] for c in edit_ws.broadcast.await_args_list if c.args[0]["type"] == "queue_changed"]
    assert len(frames) == 1 and frames[0]["action"] == "added"
    assert "tracks" not in frames[0] and "current_index" not in frames[0]


@pytest.mark.regression
@pytest.mark.asyncio
async def test_an_edit_with_no_newer_request_still_mirrors():
    service, controller, state, ws = await _service()

    await service.add_track_to_queue(9)

    assert _state_ids(state) == [1, 2, 3, 4, 9]
    assert _state_paths(state) == _engine_paths(controller)
    assert any(call.args[0]["type"] == "queue_changed" for call in ws.broadcast.await_args_list)


@pytest.mark.regression
@pytest.mark.asyncio
async def test_a_clear_does_not_stop_a_newer_set_queue_in_player_state(monkeypatch):
    """SIBLING: clear_queue's set_playing(False)/set_track(None) are gated the same way."""
    clear, controller, state, _ = await _service()
    newer_service = (await _service())[0]
    newer_service.player_state_manager = state
    newer_service.audio_player = SimpleNamespace(
        queue=controller, load_file=lambda _path: True, stop=lambda: None, play=lambda: None
    )
    cleared, release = asyncio.Event(), asyncio.Event()
    real_mutation = clear._queue_mutation

    @asynccontextmanager
    async def paused_after_engine():
        async with real_mutation():
            yield
        cleared.set()
        await release.wait()

    monkeypatch.setattr(clear, "_queue_mutation", paused_after_engine)

    clearing = asyncio.create_task(clear.clear_queue())
    await asyncio.wait_for(cleared.wait(), 5)
    await newer_service.set_queue([2, 3], start_index=0)
    release.set()
    await asyncio.wait_for(clearing, 5)

    assert state.get_state().current_track.id == 2, "the clear's late state write stopped the newer queue"
    assert _state_paths(state) == _engine_paths(controller) == ["/music/track_2.flac", "/music/track_3.flac"]
