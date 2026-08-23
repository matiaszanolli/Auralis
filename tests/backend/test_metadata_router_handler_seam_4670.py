"""
Regression tests for the metadata router's closure-to-module-level extraction
(#4670).

create_metadata_router() used to be a ~310-line closure -- every handler was a
nested `async def` reachable only by constructing the whole router with its
full dependency graph. Handlers are now module-level `async def` functions
with FastAPI Depends() defaults; a caller that wants to unit-test one
directly just passes the dependency explicitly as a keyword argument,
bypassing Depends() (and _MetadataDeps, and the router) entirely. These
tests exist to prove that seam is real, not just that it types.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.metadata import (  # noqa: E402
    BatchMetadataRequest,
    MetadataUpdateRequest,
    batch_update_metadata,
    get_editable_fields,
    get_track_metadata,
    update_track_metadata,
)

pytestmark = pytest.mark.asyncio


def _stub_repos(filepath: str = "/music/song.mp3") -> Mock:
    track = Mock()
    track.id = 1
    track.filepath = filepath
    track.format = "mp3"

    repos = Mock()
    repos.tracks.get_by_id = Mock(return_value=track)
    repos.tracks.get_by_ids = Mock(return_value={1: track})
    repos.tracks.update_metadata = Mock(return_value=track)
    repos.tracks.update_metadata_batch = Mock(return_value=[1])
    return repos


async def test_get_editable_fields_callable_with_bare_stubs():
    """No router, no _MetadataDeps, no app -- just the handler and stubs."""
    repos = _stub_repos()
    editor = MagicMock()
    editor.get_editable_fields.return_value = ["title", "artist"]
    editor.read_metadata.return_value = {"title": "T"}

    with patch("routers.metadata.validate_file_path", new=lambda p: p):
        result = await get_editable_fields(
            track_id=1,
            get_repository_factory=lambda: repos,
            metadata_editor=editor,
        )

    assert result["track_id"] == 1
    assert result["format"] == "mp3"
    assert result["editable_fields"] == ["title", "artist"]
    assert result["current_metadata"] == {"title": "T"}


async def test_get_track_metadata_callable_with_bare_stubs():
    repos = _stub_repos()
    editor = MagicMock()
    editor.read_metadata.return_value = {"title": "T", "artist": "A"}

    with patch("routers.metadata.validate_file_path", new=lambda p: p):
        result = await get_track_metadata(
            track_id=1,
            get_repository_factory=lambda: repos,
            metadata_editor=editor,
        )

    assert result == {"track_id": 1, "format": "mp3", "metadata": {"title": "T", "artist": "A"}}


async def test_update_track_metadata_callable_with_bare_stubs():
    """The tag-name -> DB-column translation (#4731) survives a direct call."""
    repos = _stub_repos()
    editor = MagicMock()
    editor.write_metadata.return_value = True
    editor.read_metadata.return_value = {"title": "T"}
    broadcast = MagicMock()
    broadcast.broadcast = AsyncMock()

    with patch("routers.metadata.validate_file_path", new=lambda p: p):
        result = await update_track_metadata(
            track_id=1,
            request=MetadataUpdateRequest(title="T", track=5, disc=1, comment="hi"),
            get_repository_factory=lambda: repos,
            metadata_editor=editor,
            broadcast_manager=broadcast,
        )

    assert result["success"] is True
    # File write keeps mutagen tag names...
    assert editor.write_metadata.call_args[0][1] == {
        "title": "T", "track": 5, "disc": 1, "comment": "hi",
    }
    # ...the DB write gets column names.
    assert repos.tracks.update_metadata.call_args.kwargs == {
        "title": "T", "track_number": 5, "disc_number": 1, "comments": "hi",
    }
    broadcast.broadcast.assert_awaited_once()


async def test_batch_update_metadata_callable_with_bare_stubs():
    repos = _stub_repos()
    editor = MagicMock()
    editor.batch_update.return_value = {
        "total": 1,
        "successful": 1,
        "failed": 0,
        "rolled_back": False,
        "results": [{"track_id": 1, "success": True, "updates": {"title": "T"}}],
    }
    broadcast = MagicMock()
    broadcast.broadcast = AsyncMock()

    with patch("routers.metadata.validate_file_path", new=lambda p, context=None: p):
        result = await batch_update_metadata(
            request=BatchMetadataRequest(
                updates=[{"track_id": 1, "metadata": {"title": "T"}}]
            ),
            get_repository_factory=lambda: repos,
            metadata_editor=editor,
            broadcast_manager=broadcast,
        )

    assert result["success"] is True
    assert result["total"] == 1
    assert result["rolled_back"] is False
    repos.tracks.update_metadata_batch.assert_called_once_with([(1, {"title": "T"})])
