"""Artwork and fingerprint caches follow the open database (#5751).

Both were hard-coded to ~/.auralis, so a library anywhere else (tests, a
portable install, a second library) wrote into the real profile and could serve
another library's `album_<id>` images.
"""

import sys
from pathlib import Path

import pytest

from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage
from auralis.analysis.fingerprint.schema import DIMENSION_SCHEMA
from auralis.library import data_dir
from auralis.library.constants import DEFAULT_DB_PATH
from auralis.library.database import LibraryDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "auralis-web" / "backend"))

from core.thumbnail_cache import artwork_cache_dirs, artwork_cache_root  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_data_dir(monkeypatch):
    monkeypatch.setattr(data_dir, "_database_data_dir", None)
    monkeypatch.delenv(data_dir.DATA_DIR_ENV, raising=False)


@pytest.fixture
def scratch_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def test_default_root_is_dot_auralis_under_home(scratch_home):
    assert data_dir.get_data_dir() == scratch_home / ".auralis"
    assert data_dir.artwork_dir() == scratch_home / ".auralis" / "artwork"
    assert data_dir.fingerprints_dir() == scratch_home / ".auralis" / "fingerprints"


def test_env_override_replaces_the_default_root(tmp_path, scratch_home, monkeypatch):
    monkeypatch.setenv(data_dir.DATA_DIR_ENV, str(tmp_path / "custom"))

    assert data_dir.get_data_dir() == tmp_path / "custom"


def test_a_custom_database_registers_its_directory(tmp_path, scratch_home):
    data_dir.register_database_location(tmp_path / "lib" / "library.db")

    assert data_dir.artwork_dir() == (tmp_path / "lib").resolve() / "artwork"


def test_the_default_database_resets_to_the_default_root(tmp_path, scratch_home):
    data_dir.register_database_location(tmp_path / "lib" / "library.db")
    data_dir.register_database_location(DEFAULT_DB_PATH)

    assert data_dir.get_data_dir() == scratch_home / ".auralis"


def test_library_database_puts_its_caches_beside_it_and_leaves_home_alone(tmp_path, scratch_home):
    library_dir = tmp_path / "portable"
    library_dir.mkdir()

    db = LibraryDatabase(str(library_dir / "library.db"))
    try:
        assert db.albums.artwork_extractor is not None
        assert (library_dir / "artwork").is_dir()
        assert not (scratch_home / ".auralis").exists(), "the real profile was touched"
    finally:
        db.shutdown()


def test_the_fingerprint_cache_and_thumbnail_root_follow_the_same_directory(tmp_path, scratch_home):
    data_dir.register_database_location(tmp_path / "lib" / "library.db")
    track = tmp_path / "song.wav"
    track.write_bytes(b"\0" * 64)
    fingerprint = {name: 0.5 for name in DIMENSION_SCHEMA}

    saved = FingerprintStorage.save(track, fingerprint, {}, sample_rate=44100, duration=1.0)

    root = (tmp_path / "lib").resolve()
    assert saved.parent == root / "fingerprints", "fingerprint cache did not follow the database"
    assert not (scratch_home / ".auralis").exists()
    assert artwork_cache_root() == root / "artwork"
    assert artwork_cache_dirs() == (root / "artwork", root / "artwork" / "thumbnails")

