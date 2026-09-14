"""
Regression tests: a deleted-on-disk track must answer 404, not 400 (#5080).

``validate_file_path()`` used to raise a bare ``PathValidationError`` for both
"this path escapes the allowed directories" and "this file is not there any
more", and every ``routers/metadata.py`` call site mapped that single type to
HTTP 400. A track whose file had been moved, deleted, or lives on an unplugged
drive — the most common desktop failure mode for a file-backed library — was
therefore reported as a malformed request, indistinguishable by the client
from a genuine traversal rejection.

The existence/is-a-file checks now raise ``PathMissingError``
(a ``PathValidationError`` subclass), which the metadata routes map to 404.
Everything else — traversal, containment, empty, unreadable — stays 400.

These tests drive the REAL ``validate_file_path`` (no side_effect patching)
against a temporarily-registered allowed directory, so they pin the end-to-end
status code rather than the router's handling of a synthetic exception.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from security.path_security import (  # noqa: E402
    PathMissingError,
    PathValidationError,
    register_allowed_directory,
    unregister_allowed_directory,
    validate_file_path,
)


@pytest.fixture
def allowed_dir(tmp_path):
    """A real directory that ``validate_file_path()`` accepts for this test."""
    music = tmp_path / "Music"
    music.mkdir()
    register_allowed_directory(music)
    try:
        yield music
    finally:
        unregister_allowed_directory(music)


def _make_app():
    from fastapi import FastAPI

    from routers.metadata import create_metadata_router

    app = FastAPI()
    app.include_router(
        create_metadata_router(
            get_repository_factory=lambda: None,
            broadcast_manager=MagicMock(),
        )
    )
    return app


def _make_repos(filepath: str) -> MagicMock:
    repos = MagicMock()
    track = MagicMock()
    track.id = 1
    track.filepath = filepath
    track.format = "flac"
    repos.tracks.get_by_id = MagicMock(return_value=track)
    return repos


def _responses_for(filepath: str):
    """Hit all three single-track metadata endpoints for one stored filepath."""
    from fastapi.testclient import TestClient

    app = _make_app()
    repos = _make_repos(filepath)

    with patch("routers.metadata.require_repository_factory", return_value=repos):
        with TestClient(app, raise_server_exceptions=False) as client:
            return {
                "fields": client.get("/api/metadata/tracks/1/fields"),
                "get": client.get("/api/metadata/tracks/1"),
                "put": client.put(
                    "/api/metadata/tracks/1", json={"title": "New Title"}
                ),
            }


class TestPathMissingErrorType:
    """The new exception must not break existing broad handlers."""

    def test_path_missing_error_is_a_path_validation_error(self):
        assert issubclass(PathMissingError, PathValidationError)

    def test_missing_file_raises_path_missing_error(self, allowed_dir):
        with pytest.raises(PathMissingError):
            validate_file_path(str(allowed_dir / "gone.flac"))

    def test_directory_raises_path_missing_error(self, allowed_dir):
        subdir = allowed_dir / "an_album"
        subdir.mkdir()
        with pytest.raises(PathMissingError):
            validate_file_path(str(subdir))

    def test_traversal_raises_plain_path_validation_error(self, allowed_dir):
        with pytest.raises(PathValidationError) as exc_info:
            validate_file_path(str(allowed_dir / ".." / "escape.flac"))
        assert not isinstance(exc_info.value, PathMissingError)

    def test_outside_allowed_dirs_raises_plain_path_validation_error(self):
        with pytest.raises(PathValidationError) as exc_info:
            validate_file_path("/etc/passwd")
        assert not isinstance(exc_info.value, PathMissingError)


class TestMissingFileReturns404:
    """A library row whose backing file is gone → 404 from all three routes."""

    def test_all_three_endpoints_return_404(self, allowed_dir):
        responses = _responses_for(str(allowed_dir / "deleted.flac"))
        for name, response in responses.items():
            assert response.status_code == 404, (
                f"{name} returned {response.status_code}, expected 404 (#5080)"
            )

    def test_404_detail_names_the_track_not_the_path(self, allowed_dir):
        missing = allowed_dir / "deleted.flac"
        for name, response in _responses_for(str(missing)).items():
            detail = response.json().get("detail", "")
            assert "track 1" in detail, f"{name}: {detail!r}"
            # #3849/#4807: never reflect the filesystem layout back to clients.
            assert str(missing) not in detail, f"{name}: {detail!r}"
            assert str(allowed_dir) not in detail, f"{name}: {detail!r}"

    def test_path_that_is_a_directory_returns_404(self, allowed_dir):
        subdir = allowed_dir / "not_a_file"
        subdir.mkdir()
        for name, response in _responses_for(str(subdir)).items():
            assert response.status_code == 404, (
                f"{name} returned {response.status_code}, expected 404 (#5080)"
            )


class TestRejectedPathStillReturns400:
    """Traversal/containment rejections must keep their 400 (no regression)."""

    def test_traversal_returns_400(self, allowed_dir):
        traversal = str(allowed_dir / ".." / ".." / "etc" / "passwd")
        for name, response in _responses_for(traversal).items():
            assert response.status_code == 400, (
                f"{name} returned {response.status_code}, expected 400 (#5080)"
            )

    def test_path_outside_allowed_directories_returns_400(self):
        for name, response in _responses_for("/etc/passwd").items():
            assert response.status_code == 400, (
                f"{name} returned {response.status_code}, expected 400 (#5080)"
            )

    def test_400_detail_stays_generic(self):
        for name, response in _responses_for("/etc/passwd").items():
            detail = response.json().get("detail", "")
            assert detail == "Invalid track filepath", f"{name}: {detail!r}"
