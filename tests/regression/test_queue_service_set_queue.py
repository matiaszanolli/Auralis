"""
Regression test: QueueService.set_queue dict iteration bug
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When commit 3dcb3eb5 (#3554) introduced the batched ``get_by_ids`` path to
avoid hundreds of milliseconds of per-track event-loop blocking, the
caller assumed the repository returned a *list* of ``Track`` objects
and iterated it as ``{t.id: t for t in raw}``. The repository actually
returns ``dict[int, Track]``, so iterating yields ints (the keys), and
every ``POST /api/player/queue`` raised
``AttributeError: 'int' object has no attribute 'id'``.

This test exercises the batched path through ``QueueService.set_queue``
with a mock repository that mimics the real ``dict[int, Track]``
contract, plus the legacy non-``get_by_ids`` fallback path for
parity.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# QueueService lives under auralis-web/backend, which is not on sys.path
# by default. Add it the same way the runtime does (config.startup).
_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.queue_service import QueueService  # noqa: E402


def _make_track(track_id: int) -> SimpleNamespace:
    """Minimal Track stand-in — only the attrs QueueService touches."""
    return SimpleNamespace(
        id=track_id,
        title=f"Track {track_id}",
        filepath=f"/music/track_{track_id}.flac",
        artists=[SimpleNamespace(name="Artist")],
        album=SimpleNamespace(title="Album"),
    )


def _build_service(repo_returns: object) -> QueueService:
    """Build a QueueService with all collaborators mocked.

    ``repo_returns`` is whatever ``tracks.get_by_ids`` should return —
    parameterised across tests to cover the dict (real) contract and the
    historical list-shaped misuse.
    """
    tracks_repo = MagicMock()
    tracks_repo.get_by_ids = MagicMock(return_value=repo_returns)

    library_manager = MagicMock()
    library_manager.tracks = tracks_repo

    # AudioPlayerWithQueue stand-in — only `queue.set_queue` is touched.
    audio_player = MagicMock()
    audio_player.queue.set_queue = MagicMock()

    # PlayerStateManager is async; coroutines mean AsyncMock.
    state_manager = MagicMock()
    state_manager.set_queue = AsyncMock()
    state_manager.set_track = AsyncMock()
    state_manager.set_playing = AsyncMock()

    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    create_track_info = MagicMock(side_effect=lambda t: SimpleNamespace(id=t.id))

    return QueueService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        library_manager=library_manager,
        connection_manager=connection_manager,
        create_track_info_fn=create_track_info,
    )


@pytest.mark.regression
@pytest.mark.asyncio
async def test_set_queue_with_dict_returning_get_by_ids():
    """The real TrackRepository contract: get_by_ids -> dict[int, Track].

    Before the fix, iterating the dict produced ints and raised
    ``AttributeError: 'int' object has no attribute 'id'``.
    """
    requested_ids = [10, 20, 30]
    tracks = {tid: _make_track(tid) for tid in requested_ids}

    service = _build_service(repo_returns=tracks)

    result = await service.set_queue(requested_ids, start_index=0)

    # No AttributeError, no exception — and the queue carries every
    # requested track in the original order.
    service.audio_player.queue.set_queue.assert_called_once()
    filepaths_passed = service.audio_player.queue.set_queue.call_args[0][0]
    assert filepaths_passed == [t.filepath for t in (tracks[10], tracks[20], tracks[30])]
    assert isinstance(result, dict)


@pytest.mark.regression
@pytest.mark.asyncio
async def test_set_queue_preserves_caller_order_dropping_missing_ids():
    """Requested ids that the repository did not return should be skipped,
    but the surviving ids must keep the caller-supplied ordering."""
    requested_ids = [30, 10, 20, 99]  # 99 doesn't exist
    tracks = {10: _make_track(10), 20: _make_track(20), 30: _make_track(30)}

    service = _build_service(repo_returns=tracks)
    await service.set_queue(requested_ids, start_index=0)

    filepaths_passed = service.audio_player.queue.set_queue.call_args[0][0]
    # Order matches caller, 99 dropped.
    assert filepaths_passed == [
        tracks[30].filepath,
        tracks[10].filepath,
        tracks[20].filepath,
    ]


@pytest.mark.regression
@pytest.mark.asyncio
async def test_set_queue_raises_when_no_tracks_resolve():
    """Empty dict from get_by_ids should surface as a ValueError, not
    a silently-empty queue."""
    service = _build_service(repo_returns={})

    with pytest.raises(ValueError, match="No valid tracks found"):
        await service.set_queue([1, 2, 3], start_index=0)


@pytest.mark.regression
@pytest.mark.asyncio
async def test_set_queue_falls_back_when_get_by_ids_missing():
    """If the repository predates the batched API, set_queue must use
    the individual get_by_id fallback path (non-regression for the
    legacy code path)."""
    tracks_repo = MagicMock(spec=['get_by_id'])  # no get_by_ids attr
    tracks_repo.get_by_id = MagicMock(side_effect=lambda tid: _make_track(tid))

    library_manager = MagicMock()
    library_manager.tracks = tracks_repo

    audio_player = MagicMock()
    audio_player.queue.set_queue = MagicMock()
    state_manager = MagicMock()
    state_manager.set_queue = AsyncMock()
    state_manager.set_track = AsyncMock()
    state_manager.set_playing = AsyncMock()
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    service = QueueService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        library_manager=library_manager,
        connection_manager=connection_manager,
        create_track_info_fn=lambda t: SimpleNamespace(id=t.id),
    )

    await service.set_queue([5, 6], start_index=0)
    assert tracks_repo.get_by_id.call_count == 2
    filepaths_passed = audio_player.queue.set_queue.call_args[0][0]
    assert filepaths_passed == ["/music/track_5.flac", "/music/track_6.flac"]
