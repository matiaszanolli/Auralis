"""
Regression tests for #4676: `artwork_updated` payload consolidation.

The three emit sites (extract/download/delete in routers/artwork.py) used to
each hand-build the broadcast dict as a raw literal, risking partial drift
(two sites updated, one forgotten) on any future payload change. They now all
funnel through `_broadcast_artwork_updated`, which is the single definition
this test asserts against.

Covers the issue's Test Plan:
1. The helper produces the exact `{type, data: {action, album_id,
   artwork_url?}}` shape for each action, with `artwork_url` absent for
   'deleted'.
2. Extract/download/delete each broadcast a frame matching that shape.
3. No inline `"type": "artwork_updated"` literal remains in the module.
"""

import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import routers.artwork as artwork_router  # noqa: E402
from routers.artwork import (  # noqa: E402
    _broadcast_artwork_updated,
    delete_album_artwork,
    download_album_artwork,
    extract_album_artwork,
)

def _stub_repos(album=None) -> MagicMock:
    repos = MagicMock()
    repos.albums.get_by_id = MagicMock(return_value=album)
    return repos


async def test_broadcast_helper_shape_for_extracted_and_downloaded():
    for action in ("extracted", "downloaded"):
        connection_manager = MagicMock()
        connection_manager.broadcast = AsyncMock()

        await _broadcast_artwork_updated(connection_manager, action, 7, "/api/albums/7/artwork")

        connection_manager.broadcast.assert_awaited_once_with({
            "type": "artwork_updated",
            "data": {"action": action, "album_id": 7, "artwork_url": "/api/albums/7/artwork"},
        })


async def test_broadcast_helper_omits_artwork_url_for_deleted():
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    await _broadcast_artwork_updated(connection_manager, "deleted", 3)

    connection_manager.broadcast.assert_awaited_once_with({
        "type": "artwork_updated",
        "data": {"action": "deleted", "album_id": 3},
    })
    assert "artwork_url" not in connection_manager.broadcast.await_args[0][0]["data"]


async def test_extract_route_broadcasts_via_shared_helper(monkeypatch):
    repos = _stub_repos(album=MagicMock(artwork_path="/old/cover.jpg"))
    repos.albums.extract_and_save_artwork = MagicMock(return_value="/new/cover.jpg")
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()
    monkeypatch.setattr("routers.artwork._purge_album_thumbnails", lambda *a: 0)

    await extract_album_artwork(album_id=7, repos=repos, connection_manager=connection_manager)

    connection_manager.broadcast.assert_awaited_once_with({
        "type": "artwork_updated",
        "data": {"action": "extracted", "album_id": 7, "artwork_url": "/api/albums/7/artwork"},
    })


async def test_delete_route_broadcasts_via_shared_helper(monkeypatch):
    repos = _stub_repos(album=MagicMock(artwork_path="/art/cover.jpg"))
    repos.albums.delete_artwork = MagicMock(return_value=True)
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()
    monkeypatch.setattr("routers.artwork._purge_album_thumbnails", lambda *a: 0)

    await delete_album_artwork(album_id=3, repos=repos, connection_manager=connection_manager)

    connection_manager.broadcast.assert_awaited_once_with({
        "type": "artwork_updated",
        "data": {"action": "deleted", "album_id": 3},
    })


async def test_download_route_broadcasts_via_shared_helper(monkeypatch):
    album = MagicMock(artwork_path=None)
    album.artist.name = "Test Artist"
    album.title = "Test Album"
    repos = _stub_repos(album=album)
    repos.albums.update_artwork_path = MagicMock(return_value=album)
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()
    monkeypatch.setattr("routers.artwork._purge_album_thumbnails", lambda *a: 0)

    mock_downloader = AsyncMock()
    mock_downloader.download_artwork.return_value = "/downloaded/cover.jpg"
    monkeypatch.setattr(
        "services.artwork_downloader.get_artwork_downloader", lambda: mock_downloader
    )

    await download_album_artwork(album_id=9, repos=repos, connection_manager=connection_manager)

    connection_manager.broadcast.assert_awaited_once_with({
        "type": "artwork_updated",
        "data": {"action": "downloaded", "album_id": 9, "artwork_url": "/api/albums/9/artwork"},
    })


async def test_download_route_missing_album_still_never_broadcasts():
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    with pytest.raises(HTTPException):
        await download_album_artwork(
            album_id=99, repos=_stub_repos(album=None), connection_manager=connection_manager
        )

    connection_manager.broadcast.assert_not_awaited()


def test_no_inline_artwork_updated_literal_remains():
    """Static check (issue's Test Plan #3): every emit site must go through
    the shared helper, not an inline dict literal."""
    assert artwork_router.__file__ is not None
    source = Path(artwork_router.__file__).read_text()
    # Exactly one occurrence: inside _broadcast_artwork_updated itself.
    assert len(re.findall(r'"type":\s*"artwork_updated"', source)) == 1
