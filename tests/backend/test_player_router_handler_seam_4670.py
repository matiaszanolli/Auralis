"""
Regression tests for the player router's closure-to-module-level extraction
(#4670).

create_player_router() used to be a 515-line closure -- every handler was a
nested `async def` reachable only by constructing the whole router with its
full dependency graph. Handlers are now module-level `async def` functions
with FastAPI Depends() defaults; a caller that wants to unit-test one
directly just passes the dependency/service explicitly as a keyword
argument, bypassing Depends() (and _PlayerDeps, and the router) entirely.
These tests exist to prove that seam is real, not just that it types.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.player import (  # noqa: E402
    get_player_status,
    next_track,
    previous_track,
    QueueHistoryStateSnapshot,
    RecordQueueHistoryRequest,
    record_queue_history,
    seek_position,
    SeekRequest,
    set_volume,
    SetVolumeRequest,
    undo_queue_operation,
)
from services.errors import InvalidRequest, ServiceUnavailable  # noqa: E402

pytestmark = pytest.mark.asyncio


async def test_get_player_status_callable_with_a_bare_stub_service():
    """No router, no _PlayerDeps, no app -- just the handler and a stub."""
    stub_service = MagicMock()
    stub_service.get_status = AsyncMock(return_value={"status": "playing"})

    result = await get_player_status(service=stub_service)

    assert result == {"status": "playing"}
    stub_service.get_status.assert_awaited_once()


async def test_set_volume_callable_with_a_bare_stub_service():
    # #5050: the service's rounded 0-100 int -- e.g. 42.7 normalized then
    # denormalized and rounded -- deliberately differs from the fractional
    # request body below, so a route that (as it used to, #3204) substitutes
    # body.volume back into the response would disagree with what the
    # service itself would broadcast over WS for this same call.
    stub_service = MagicMock()
    stub_service.set_volume = AsyncMock(return_value={"message": "Volume set", "volume": 43})

    result = await set_volume(SetVolumeRequest(volume=42.7), service=stub_service)

    # 42.7/100 normalized before the service call; the response volume is
    # whatever the service returned -- NOT body.volume -- preserved by the
    # extraction, not just the direct-call plumbing.
    stub_service.set_volume.assert_awaited_once()
    assert stub_service.set_volume.await_args.args[0] == pytest.approx(0.427)
    assert result["volume"] == 43


async def test_set_volume_maps_service_unavailable_to_503():
    """#5268: the audio-player-unavailable case must reach the client as a
    retryable 503, not a 400 that implies the request itself was bad."""
    stub_service = MagicMock()
    stub_service.set_volume = AsyncMock(side_effect=ServiceUnavailable("Audio player not available"))

    with pytest.raises(HTTPException) as exc_info:
        await set_volume(SetVolumeRequest(volume=50), service=stub_service)

    assert exc_info.value.status_code == 503


async def test_set_volume_maps_plain_value_error_to_400():
    """Companion to the above: a genuinely bad request (an untyped
    ValueError from the service) must still map to 400, unaffected by the
    503 carve-out for ServiceUnavailable."""
    stub_service = MagicMock()
    stub_service.set_volume = AsyncMock(side_effect=ValueError("Volume must be between 0.0 and 1.0"))

    with pytest.raises(HTTPException) as exc_info:
        await set_volume(SetVolumeRequest(volume=50), service=stub_service)

    assert exc_info.value.status_code == 400


async def test_next_track_callable_with_a_bare_stub_service():
    stub_service = MagicMock()
    stub_service.next_track = AsyncMock(return_value={"message": "Skipped"})

    result = await next_track(service=stub_service)

    assert result == {"message": "Skipped"}


async def test_previous_track_callable_with_a_bare_stub_service():
    stub_service = MagicMock()
    stub_service.previous_track = AsyncMock(return_value={"message": "Skipped back"})

    result = await previous_track(service=stub_service)

    assert result == {"message": "Skipped back"}


# ---------------------------------------------------------------------------
# #5338: the 6 remaining hard-coded-status sites now go through
# raise_for_service_error (or BadRequestError for the two repository-level
# sites), mirroring set_volume's #5268 fix above instead of guessing one
# fixed status per call site regardless of the actual failure.
# ---------------------------------------------------------------------------

async def test_get_player_status_maps_service_unavailable_to_503():
    stub_service = MagicMock()
    stub_service.get_status = AsyncMock(
        side_effect=ServiceUnavailable("Player state manager not available")
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_player_status(service=stub_service)

    assert exc_info.value.status_code == 503


async def test_seek_maps_service_unavailable_to_503():
    stub_service = MagicMock()
    stub_service.seek = AsyncMock(side_effect=ServiceUnavailable("Audio player not available"))

    with pytest.raises(HTTPException) as exc_info:
        await seek_position(
            SeekRequest(position=30.0), player_state_manager=None, service=stub_service
        )

    assert exc_info.value.status_code == 503


async def test_seek_negative_position_maps_to_400_not_503():
    """The headline bug (#5338): a negative-position rejection is bad
    input, not a service outage -- it must reach the client as 400, not the
    503 every ValueError used to get here regardless of cause. Pydantic's
    own SeekRequest validator already rejects a negative position with 422
    before this handler ever runs (see SeekRequest.validate_position), so
    this exercises the router's mapping logic directly against what the
    service itself would raise for any caller that reaches it -- proving
    the dispatch is type-based, not just coincidentally still 503."""
    stub_service = MagicMock()
    stub_service.seek = AsyncMock(side_effect=InvalidRequest("Position must be non-negative"))

    with pytest.raises(HTTPException) as exc_info:
        await seek_position(
            SeekRequest(position=30.0), player_state_manager=None, service=stub_service
        )

    assert exc_info.value.status_code == 400


async def test_next_track_maps_service_unavailable_to_503():
    stub_service = MagicMock()
    stub_service.next_track = AsyncMock(side_effect=ServiceUnavailable("Audio player not available"))

    with pytest.raises(HTTPException) as exc_info:
        await next_track(service=stub_service)

    assert exc_info.value.status_code == 503


async def test_previous_track_maps_service_unavailable_to_503():
    stub_service = MagicMock()
    stub_service.previous_track = AsyncMock(
        side_effect=ServiceUnavailable("Audio player not available")
    )

    with pytest.raises(HTTPException) as exc_info:
        await previous_track(service=stub_service)

    assert exc_info.value.status_code == 503


def _history_request(operation: str = "set") -> RecordQueueHistoryRequest:
    return RecordQueueHistoryRequest(
        operation=operation,
        state_snapshot=QueueHistoryStateSnapshot(track_ids=[1, 2, 3], current_index=0),
    )


async def test_record_queue_history_maps_repo_value_error_to_400():
    """Repository-level ValueError (not a typed ServiceError) stays 400,
    now via BadRequestError rather than a bare HTTPException(400) -- same
    status, consistent construction (#5338)."""
    repo = MagicMock()
    repo.push_to_history = MagicMock(side_effect=ValueError("bad snapshot"))

    with pytest.raises(HTTPException) as exc_info:
        await record_queue_history(_history_request(), repo=repo)

    assert exc_info.value.status_code == 400


async def test_undo_queue_operation_maps_repo_value_error_to_400():
    repo = MagicMock()
    repo.undo = MagicMock(side_effect=ValueError("corrupt history entry"))

    with pytest.raises(HTTPException) as exc_info:
        await undo_queue_operation(
            repo=repo,
            queue_service=MagicMock(),
            player_state_manager=None,
            connection_manager=MagicMock(),
        )

    assert exc_info.value.status_code == 400
