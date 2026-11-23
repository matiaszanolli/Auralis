"""Tracks created by POST /api/files/upload pass path validation, and uploads follow AURALIS_DATA_DIR (#6513).

The upload route stored files in ~/.auralis/uploads, which no allowlist entry covered, so every
path-validated route (streaming, metadata, lyrics) refused the tracks it had just created; it also
ignored AURALIS_DATA_DIR. The uploads directory is now data_dir.uploads_dir() and is on the allowlist
on its own, never the whole data directory (#2562).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.data_dir import uploads_dir  # noqa: E402
from security.path_errors import PathValidationError  # noqa: E402
from security.path_security import validate_file_path  # noqa: E402


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AURALIS_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data" / "uploads").mkdir(parents=True)
    return tmp_path / "data"


def test_the_uploads_directory_follows_the_data_dir_override(data_root):
    assert uploads_dir() == data_root / "uploads"


def test_an_uploaded_track_passes_path_validation(data_root):
    track = data_root / "uploads" / "3f2a.flac"
    track.write_bytes(b"fLaC")

    assert validate_file_path(str(track)) == track.resolve()


def test_the_rest_of_the_data_directory_stays_off_the_allowlist(data_root):
    library = data_root / "library.db"
    library.write_bytes(b"SQLite format 3")

    with pytest.raises(PathValidationError):
        validate_file_path(str(library))
