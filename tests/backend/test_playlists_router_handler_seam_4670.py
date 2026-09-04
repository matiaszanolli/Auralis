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
    AddTracksRequest,
    CreatePlaylistRequest,
    add_tracks_to_playlist,
    clear_playlist,
    create_playlist,
    get_playlists,
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
