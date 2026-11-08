"""v30 -> v31 makes the next scan re-read every track so albums get their ALBUMARTIST owner (#6332)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The tag is stored nowhere, so SQL cannot merge the compilations v30 fragmented; only
the files know. The scanner skips a file whose stored mtime matches, so the migration
clears ``tracks.file_mtime`` (NULL already means "unknown, re-read once" to the
scanner). The re-read must not throw away a stored fingerprint.
"""

import re
import sqlite3
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

import auralis.library.migrations as migrations_pkg
from auralis.__version__ import __db_schema_version__
from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Album, Artist, Track
from auralis.library.repositories.track_repository_mutation import _audio_changed
from auralis.library.scanner.batch_processor import BatchProcessor

MIGRATIONS = Path(migrations_pkg.__file__).parent


def _v30_library(db_path: Path, audio: Path) -> None:
    """A v30 library: three fragments of one compilation, each with a scanner watermark."""
    stat = audio.stat()
    with MigrationManager(str(db_path)) as manager:
        assert manager.initialize_fresh_database()
        with manager.engine.begin() as conn:
            conn.execute(text("UPDATE schema_version SET version = 30"))
        with sessionmaker(bind=manager.engine)() as session:
            for n, name in enumerate(["A", "B", "C"], start=1):
                artist = Artist(name=name, normalized_name=name.lower())
                album = Album(title="Hits", artist=artist)
                session.add(Track(
                    id=n, title=f"T{n}", filepath=str(audio) if n == 1 else f"{audio}.{n}", filepath_key=f"k{n}",
                    duration=10.0, sample_rate=44100, channels=2, format="FLAC",
                    filesize=stat.st_size, file_mtime=stat.st_mtime, album=album,
                ))
            session.commit()


def _rows(db_path: Path, sql: str) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_the_scanner_skips_an_unchanged_file_before_the_migration_and_rereads_it_after(tmp_path):
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"x" * 64)
    db_path = tmp_path / "library.db"
    _v30_library(db_path, audio)

    with sessionmaker(bind=MigrationManager(str(db_path)).engine)() as session:
        before = session.get(Track, 1)
        assert BatchProcessor._skip_existing_track(before, str(audio), True) is True

    with MigrationManager(str(db_path)) as manager:
        assert manager.migrate_to_latest()
        assert manager.get_current_version() == __db_schema_version__
        with sessionmaker(bind=manager.engine)() as session:
            after = session.get(Track, 1)
            assert BatchProcessor._skip_existing_track(after, str(audio), True) is False


def test_only_the_watermark_is_cleared(tmp_path):
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"x" * 64)
    db_path = tmp_path / "library.db"
    _v30_library(db_path, audio)

    with MigrationManager(str(db_path)) as manager:
        assert manager.migrate_to_latest()

    assert _rows(db_path, "SELECT COUNT(*) FROM tracks WHERE file_mtime IS NOT NULL") == [(0,)]
    assert _rows(db_path, "SELECT COUNT(*), SUM(filesize) FROM tracks") == [(3, 3 * 64)]
    assert _rows(db_path, "SELECT COUNT(*) FROM albums") == [(3,)]  # nothing is merged blindly


def test_a_reread_after_the_migration_does_not_discard_the_fingerprint():
    """A NULL stored mtime is not a changed recording, so update_by_filepath keeps the fingerprint."""
    track = Track(duration=10.0, sample_rate=44100, channels=2, format="FLAC", filesize=64, file_mtime=None)
    rescan = {"duration": 10.0, "sample_rate": 44100, "channels": 2, "format": "FLAC",
              "filesize": 64, "file_mtime": 1_700_000_000.0}

    assert _audio_changed(track, rescan) is False


def test_the_migration_is_a_single_forward_step_at_the_head_of_the_chain():
    files = sorted(p.name for p in MIGRATIONS.glob("migration_v*_to_v*.sql"))
    edges = [tuple(int(n) for n in re.findall(r"v(\d+)_to_v(\d+)", f)[0]) for f in files]

    assert (30, 31) in edges
    assert max(to for _, to in edges) == __db_schema_version__


def test_end_to_end_the_scan_after_the_migration_merges_a_fragmented_compilation(tmp_path):
    """Real tagged FLACs, a library stored the v30 way, the real migration, the real scanner."""
    import numpy as np
    import soundfile as sf
    from mutagen.flac import FLAC

    from auralis.library.database import LibraryDatabase
    from auralis.library.scanner.scanner import LibraryScanner

    music = tmp_path / "music"
    music.mkdir()
    paths = []
    for n, artist in enumerate(["A", "B", "C"], start=1):
        path = music / f"{n}.flac"
        sf.write(str(path), np.random.default_rng(n).uniform(-0.1, 0.1, (22050, 2)).astype("float32"), 44100)
        tags = FLAC(str(path))
        tags.update({"ARTIST": artist, "ALBUM": "Hits", "ALBUMARTIST": "Various Artists", "TITLE": f"T{n}"})
        tags.save()
        paths.append(path)

    db_path = tmp_path / "library.db"
    library = LibraryDatabase(str(db_path))
    for n, path in enumerate(paths, start=1):  # as v30 stored them: owned by the track artist, watermark stamped
        library.tracks.add({
            "filepath": str(path), "title": f"T{n}", "duration": 0.5, "sample_rate": 44100, "channels": 2,
            "format": "FLAC", "artists": ["ABC"[n - 1]], "album": "Hits",
            "filesize": path.stat().st_size, "file_mtime": path.stat().st_mtime,
        })
    library.shutdown()
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE schema_version SET version = 30")
    conn.commit()
    conn.close()

    library = LibraryDatabase(str(db_path))  # opening a v30 library runs the migration
    try:
        assert library.stats.get_library_stats()["total_albums"] == 3

        scan = LibraryScanner(library).scan_directories([str(music)])
        assert (scan.files_updated, scan.files_skipped, scan.files_failed) == (3, 0, 0)

        stats = library.stats.get_library_stats()
        assert (stats["total_tracks"], stats["total_albums"]) == (3, 1)
        with library.SessionLocal() as s:
            owners = s.execute(
                select(Artist.name).join(Album, Album.artist_id == Artist.id)
            ).scalars().all()
        assert owners == ["Various Artists"]

        again = LibraryScanner(library).scan_directories([str(music)])
        assert (again.files_updated, again.files_skipped) == (0, 3)  # the watermark was stamped again
    finally:
        library.shutdown()
