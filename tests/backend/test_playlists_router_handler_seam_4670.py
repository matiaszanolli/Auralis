"""
Regression tests for the playlists router's closure-to-module-level extraction
(#4670).

create_playlists_router() used to be a ~400-line closure -- every handler was a
nested `async def` reachable only by constructing the whole router with its
full dependency graph. Handlers are now module-level `async def` functions
with FastAPI Depends() defaults; a caller that wants to unit-test one
directly just passes the repos/connection_manager explicitly as a keyword
argument, bypassing Depends() (and _PlaylistsDeps, and the router) entirely.
These tests exist to prove that seam is real, not just that it types.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.playlists import (  # noqa: E402
    add_track_to_playlist,
    add_tracks_to_playlist,
    clear_playlist,
    create_playlist,
    delete_playlist,
    get_playlists,
    remove_track_from_playlist,
    reorder_playlist_track,
    update_playlist,
)
from routers.playlists_models import (  # noqa: E402
    AddTrackRequest,
    AddTracksRequest,
    CreatePlaylistRequest,
    ReorderTrackRequest,
    UpdatePlaylistRequest,
)

pytestmark = pytest.mark.asyncio


async def test_get_playlists_callable_with_a_bare_stub_repo():
    """No router, no _PlaylistsDeps, no app -- just the handler and a stub."""
    stub_repos = MagicMock()
    stub_repos.playlists.get_all.return_value = ([], 7)

    result = await get_playlists(limit=10, offset=0, repos=stub_repos)

    stub_repos.playlists.get_all.assert_called_once_with(limit=10, offset=0)
    assert result["total"] == 7
    assert result["limit"] == 10
    assert result["offset"] == 0
    # 0 returned on a page-0 request of a 7-row total -> more pages remain
    assert result["has_more"] is True


async def test_create_playlist_broadcasts_through_an_injected_manager():
    playlist = MagicMock()
    playlist.id = 3
    playlist.name = "Road trip"
    # serialize_object() requires to_dict() to return a dict (#5803).
    playlist.to_dict.return_value = {"id": 3, "name": "Road trip"}
    stub_repos = MagicMock()
    stub_repos.playlists.create.return_value = playlist
    stub_manager = MagicMock()
    stub_manager.broadcast = AsyncMock()

    result = await create_playlist(
        CreatePlaylistRequest(name="Road trip"),
        repos=stub_repos,
        connection_manager=stub_manager,
    )

    assert result["message"] == "Playlist 'Road trip' created"
    stub_manager.broadcast.assert_awaited_once()
    assert stub_manager.broadcast.await_args.args[0]["type"] == "playlist_created"


async def test_add_tracks_to_playlist_accepts_duplicate_only_add():
    """An idempotent all-duplicate add is a successful no-op (#5263)."""
    stub_repos = MagicMock()
    stub_repos.playlists.get_by_id.return_value = MagicMock()
    stub_repos.playlists.add_tracks.return_value = 0
    stub_manager = MagicMock()
    stub_manager.broadcast = AsyncMock()

    result = await add_tracks_to_playlist(
        5,
        AddTracksRequest(track_ids=[1, 2]),
        repos=stub_repos,
        connection_manager=stub_manager,
    )

    assert result["added_count"] == 0
    stub_repos.playlists.get_by_id.assert_called_once_with(5)
    stub_repos.playlists.add_tracks.assert_called_once_with(5, [1, 2])
    stub_manager.broadcast.assert_not_awaited()


async def test_add_tracks_to_playlist_rejects_missing_playlist():
    """A missing playlist is distinct from an idempotent no-op (#5263)."""
    from fastapi import HTTPException

    stub_repos = MagicMock()
    stub_repos.playlists.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await add_tracks_to_playlist(
            999,
            AddTracksRequest(track_ids=[1]),
            repos=stub_repos,
            connection_manager=MagicMock(),
        )

    assert exc.value.status_code == 404
    stub_repos.playlists.add_tracks.assert_not_called()


async def test_clear_playlist_callable_with_bare_stubs():
    stub_repos = MagicMock()
    stub_repos.playlists.clear.return_value = True
    stub_manager = MagicMock()
    stub_manager.broadcast = AsyncMock()

    result = await clear_playlist(9, repos=stub_repos, connection_manager=stub_manager)

    assert result == {"message": "Playlist cleared"}
    stub_repos.playlists.clear.assert_called_once_with(9)
    assert stub_manager.broadcast.await_args.args[0]["data"]["action"] == "cleared"


# ---------------------------------------------------------------------------
# #6498: the empty-update 400 and every mutating handler's broadcast, asserted by value. The frontend
# playlist list refreshes on these frames, so a renamed type, action or key must fail a test.
# ---------------------------------------------------------------------------


def _manager() -> MagicMock:
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    return manager


async def test_an_update_with_neither_name_nor_description_is_400():
    from fastapi import HTTPException

    stub_repos = MagicMock()
    manager = _manager()

    with pytest.raises(HTTPException) as exc:
        await update_playlist(4, UpdatePlaylistRequest(), repos=stub_repos, connection_manager=manager)

    assert exc.value.status_code == 400
    assert "No update data provided" in str(exc.value.detail)
    stub_repos.playlists.update.assert_not_called()
    manager.broadcast.assert_not_awaited()


def _stub_repos_that_succeed() -> MagicMock:
    stub_repos = MagicMock()
    stub_repos.playlists.get_by_id.return_value = MagicMock()
    stub_repos.playlists.update.return_value = True
    stub_repos.playlists.add_tracks.return_value = 2
    stub_repos.playlists.add_track.return_value = True
    stub_repos.playlists.reorder_track.return_value = True
    stub_repos.playlists.remove_track.return_value = True
    stub_repos.playlists.clear.return_value = True
    stub_repos.playlists.delete.return_value = True
    return stub_repos


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (lambda **kw: update_playlist(6, UpdatePlaylistRequest(name="New"), **kw),
         {"type": "playlist_updated", "data": {"playlist_id": 6, "action": "renamed"}}),
        (lambda **kw: add_tracks_to_playlist(6, AddTracksRequest(track_ids=[1, 2]), **kw),
         {"type": "playlist_updated", "data": {"playlist_id": 6, "action": "track_added"}}),
        (lambda **kw: add_track_to_playlist(6, AddTrackRequest(track_id=1, position=0), **kw),
         {"type": "playlist_updated", "data": {"playlist_id": 6, "action": "track_added"}}),
        (lambda **kw: reorder_playlist_track(6, ReorderTrackRequest(from_index=0, to_index=1), **kw),
         {"type": "playlist_updated", "data": {"playlist_id": 6, "action": "reordered"}}),
        (lambda **kw: remove_track_from_playlist(6, 1, **kw),
         {"type": "playlist_updated", "data": {"playlist_id": 6, "action": "track_removed"}}),
        (lambda **kw: clear_playlist(6, **kw),
         {"type": "playlist_updated", "data": {"playlist_id": 6, "action": "cleared"}}),
        (lambda **kw: delete_playlist(6, **kw),
         {"type": "playlist_deleted", "data": {"playlist_id": 6}}),
    ],
    ids=["rename", "add-tracks", "add-track", "reorder", "remove-track", "clear", "delete"],
)
async def test_each_mutating_handler_broadcasts_its_frame(call, expected):
    manager = _manager()

    await call(repos=_stub_repos_that_succeed(), connection_manager=manager)

    manager.broadcast.assert_awaited_once_with(expected)
