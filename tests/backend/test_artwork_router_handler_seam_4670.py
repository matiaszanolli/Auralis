"""
Regression tests for the artwork router's closure-to-module-level extraction
(#4670).

create_artwork_router() used to be a 330-line closure -- every handler was a
nested `async def` reachable only by constructing the whole router with its
full dependency graph. Handlers are now module-level `async def` functions
with FastAPI Depends() defaults; a caller that wants to unit-test one
directly just passes the repository factory / connection manager explicitly
as a keyword argument, bypassing Depends() (and _ArtworkDeps, and the router)
entirely. These tests exist to prove that seam is real, not just that it
types.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.artwork import (  # noqa: E402
    delete_album_artwork,
    download_album_artwork,
    extract_album_artwork,
    get_album_artwork,
)

pytestmark = pytest.mark.asyncio


def _stub_repos(album=None) -> MagicMock:
    repos = MagicMock()
    repos.albums.get_by_id = MagicMock(return_value=album)
    return repos


async def test_get_album_artwork_callable_with_bare_stubs():
    """No router, no _ArtworkDeps, no app -- just the handler and stubs."""
    with pytest.raises(HTTPException) as exc_info:
        await get_album_artwork(
            album_id=1,
            request=MagicMock(),
            size=None,
            repos=_stub_repos(album=None),
        )

    # NotFoundError is an HTTPException subclass -- the missing-album branch
    # is reachable without building the router at all.
    assert exc_info.value.status_code == 404


async def test_extract_album_artwork_callable_with_bare_stubs(monkeypatch):
    repos = _stub_repos(album=MagicMock(artwork_path="/old/cover.jpg"))
    repos.albums.extract_and_save_artwork = MagicMock(return_value="/new/cover.jpg")
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()
    monkeypatch.setattr("routers.artwork._purge_album_thumbnails", lambda *a: 0)

    result = await extract_album_artwork(
        album_id=7, repos=repos, connection_manager=connection_manager
    )

    assert result == {
        "message": "Artwork extracted successfully",
        "artwork_url": "/api/albums/7/artwork",
        "album_id": 7,
    }
    connection_manager.broadcast.assert_awaited_once()
    assert connection_manager.broadcast.await_args[0][0]["data"]["action"] == "extracted"


async def test_delete_album_artwork_callable_with_bare_stubs(monkeypatch):
    repos = _stub_repos(album=MagicMock(artwork_path="/art/cover.jpg"))
    repos.albums.delete_artwork = MagicMock(return_value=True)
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()
    purged: list = []
    monkeypatch.setattr(
        "routers.artwork._purge_album_thumbnails", lambda *a: purged.extend(a) or 0
    )

    result = await delete_album_artwork(
        album_id=3, repos=repos, connection_manager=connection_manager
    )

    assert result == {"message": "Artwork deleted successfully", "album_id": 3}
    # The source path is read BEFORE delete_artwork clears it (#4532) --
    # preserved by the extraction, not just the direct-call plumbing.
    assert purged == ["/art/cover.jpg"]


async def test_download_album_artwork_missing_album_callable_with_bare_stubs():
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await download_album_artwork(
            album_id=99,
            repos=_stub_repos(album=None),
            connection_manager=connection_manager,
        )

    assert exc_info.value.status_code == 404
    connection_manager.broadcast.assert_not_awaited()
