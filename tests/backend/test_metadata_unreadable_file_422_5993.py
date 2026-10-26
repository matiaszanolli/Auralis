"""
Regression tests: a corrupt audio file answers one fixed 422, never a path (#5993)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

mutagen reports an unidentifiable file as ``None`` (-> the editor's
``ValueError`` naming the absolute path) for m4a/ogg/opus/wma/au and as a
format-specific ``MutagenError`` for flac/mp3/wav/aiff. PUT turned the former
into ``400 "Invalid metadata: ...<absolute path>"`` and the rest into a bare 500;
GET always answered 500. All three single-track routes now answer the same
``422 "Unreadable or unsupported audio file"``, and ``Invalid metadata`` stays
reserved for the request's own values.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.metadata_editor import MUTAGEN_AVAILABLE  # noqa: E402
from security.path_allowlist import (  # noqa: E402
    register_allowed_directory,
    unregister_allowed_directory,
)

pytestmark = pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed")

_DETAIL = "Unreadable or unsupported audio file"
_EXTENSIONS = ["m4a", "ogg", "opus", "wma", "au", "flac", "mp3", "wav", "aiff"]


@pytest.fixture
def allowed_dir(tmp_path):
    music = tmp_path / "Music"
    music.mkdir()
    register_allowed_directory(music)
    try:
        yield music
    finally:
        unregister_allowed_directory(music)


def _responses_for(filepath: Path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from routers.metadata import create_metadata_router

    app = FastAPI()
    app.include_router(
        create_metadata_router(get_repository_factory=lambda: None, broadcast_manager=MagicMock())
    )
    track = MagicMock(id=1, filepath=str(filepath), format=filepath.suffix.lstrip("."))
    repos = MagicMock()
    repos.tracks.get_by_id = MagicMock(return_value=track)

    with patch("routers.dependencies.require_repository_factory", return_value=repos):
        with TestClient(app, raise_server_exceptions=False) as client:
            return {
                "fields": client.get("/api/metadata/tracks/1/fields"),
                "get": client.get("/api/metadata/tracks/1"),
                "put": client.put("/api/metadata/tracks/1", json={"title": "New Title"}),
            }


@pytest.mark.parametrize("ext", _EXTENSIONS)
def test_corrupt_file_gets_the_same_fixed_422_on_every_route(allowed_dir, ext):
    junk = allowed_dir / f"junk.{ext}"
    junk.write_bytes(os.urandom(5000))

    for route, response in _responses_for(junk).items():
        assert response.status_code == 422, (route, response.text)
        assert response.json() == {"detail": _DETAIL}, route
        assert str(allowed_dir) not in response.text, route


def test_invalid_request_values_still_answer_400(allowed_dir):
    """The ``Invalid metadata`` 400 stays for ValueErrors about the request itself."""
    from auralis.library.metadata_editor import MetadataEditor

    ok = allowed_dir / "ok.mp3"
    ok.write_bytes(b"\0" * 64)
    with patch.object(MetadataEditor, "write_metadata", side_effect=ValueError("year must be numeric")):
        responses = _responses_for(ok)

    assert responses["put"].status_code == 400
    assert responses["put"].json() == {"detail": "Invalid metadata: year must be numeric"}
