"""
Regression tests for the albums router's closure-to-module-level extraction
(#4670).

create_albums_router() used to be one 219-line closure -- every handler was a
nested `async def` reachable only by constructing the whole router with its
dependency graph. Handlers are now module-level `async def` functions with
FastAPI Depends() defaults; a caller that wants to unit-test one directly just
passes `repos` explicitly as a keyword argument, bypassing Depends() (and
_AlbumsDeps, and the router) entirely. These tests exist to prove that seam is
real, not just that it types.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import HTTPException  # noqa: E402

from routers.albums import (  # noqa: E402
    get_album,
    get_album_fingerprint,
    get_album_tracks,
    get_albums,
)

pytestmark = pytest.mark.asyncio


def _stub_album(album_id: int = 1, tracks=None):
    album = MagicMock()
    album.id = album_id
    album.title = "Test Album"
    album.artist.name = "Test Artist"
    album.year = 2024
    album.artwork_path = None
    album.tracks = tracks if tracks is not None else []
    return album


async def test_get_albums_callable_with_a_bare_stub_repos():
    """No router, no _AlbumsDeps, no app -- just the handler and a stub."""
    repos = MagicMock()
    repos.albums.get_all.return_value = ([], 0)

    result = await get_albums(limit=10, offset=0, search=None, order_by='title', repos=repos)

    repos.albums.get_all.assert_called_once_with(limit=10, offset=0, order_by='title')
    repos.albums.search.assert_not_called()
    assert result == {
        "albums": [],
        "total": 0,
        "offset": 0,
        "limit": 10,
        "has_more": False,
    }


async def test_get_albums_routes_a_search_to_the_search_repo():
    """The search/no-search branch survived the extraction."""
    repos = MagicMock()
    repos.albums.search.return_value = ([], 0)

    await get_albums(limit=5, offset=0, search="dark", order_by='year', repos=repos)

    repos.albums.search.assert_called_once_with("dark", limit=5, offset=0, order_by='year')
    repos.albums.get_all.assert_not_called()


async def test_get_album_missing_album_raises_404():
    repos = MagicMock()
    repos.albums.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_album(999, repos=repos)

    assert exc_info.value.status_code == 404


async def test_get_album_tracks_derives_genre_and_sorts():
    """Business logic is unchanged by the move: derived genre + disc/track sort."""
    track_a = MagicMock()
    track_b = MagicMock()
    repos = MagicMock()
    repos.albums.get_by_id.return_value = _stub_album(tracks=[track_a, track_b])

    # serialize_tracks() is stubbed so the assertions below land on the logic
    # the handler itself owns (genre derivation + disc/track sort), not on the
    # shared serializer.
    with pytest.MonkeyPatch.context() as mp:
        import routers.albums as albums_mod
        mp.setattr(
            albums_mod,
            "serialize_tracks",
            lambda tracks: [
                {"disc_number": 1, "track_number": 2, "genres": ["Rock"]},
                {"disc_number": 1, "track_number": 1, "genres": ["Rock", "Jazz"]},
            ],
        )
        result = await get_album_tracks(1, repos=repos)

    assert result["album_id"] == 1
    assert result["artist"] == "Test Artist"
    assert result["genre"] == "Rock"
    assert result["artwork_url"] is None
    assert result["total_tracks"] == 2
    assert [t["track_number"] for t in result["tracks"]] == [1, 2]


async def test_get_album_fingerprint_without_tracks_raises_404():
    repos = MagicMock()
    repos.albums.get_by_id.return_value = _stub_album(tracks=[])

    with pytest.raises(HTTPException) as exc_info:
        await get_album_fingerprint(1, repos=repos)

    assert exc_info.value.status_code == 404
    assert "has no tracks" in exc_info.value.detail
