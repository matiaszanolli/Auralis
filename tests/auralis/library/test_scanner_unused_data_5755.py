"""
Scanner and schema no longer carry unread data (#5755)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The scanner used to hash the first and last chunk of every file (two extra
reads per file on top of the probe) into ``AudioFileInfo.file_hash``, which
nothing ever read, and ``tracks`` kept three indexes on ``fingerprint_*``
columns that no production code queries or writes.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest
import soundfile as sf
from sqlalchemy import text

from auralis.library.migration_manager import MigrationManager
from auralis.library.scan_models import AudioFileInfo
from auralis.library.schema_indexes import create_missing_declared_indexes
from auralis.library.scanner.audio_analyzer import AudioAnalyzer

DROPPED_INDEXES = {
    'idx_tracks_fingerprint_status',
    'idx_tracks_fingerprint_queue',
    'idx_tracks_fingerprint_computed_at',
}


def _track_index_names(engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA index_list(tracks)")).fetchall()
    return {row[1] for row in rows}


def test_extract_audio_info_does_not_hash_the_file(tmp_path):
    wav = tmp_path / "tone.wav"
    sf.write(str(wav), np.zeros(4410, dtype=np.float32), 44100)

    info = AudioAnalyzer().extract_audio_info(str(wav))

    assert info is not None
    assert info.sample_rate == 44100
    assert not hasattr(AudioAnalyzer, 'calculate_file_hash')
    assert 'file_hash' not in AudioFileInfo.__dataclass_fields__


def test_fresh_database_has_no_fingerprint_indexes(tmp_path):
    with MigrationManager(str(tmp_path / "fresh.db")) as manager:
        assert manager.initialize_fresh_database()
        # The startup repair must not bring the indexes back either.
        create_missing_declared_indexes(manager.engine)
        assert not DROPPED_INDEXES & _track_index_names(manager.engine)


def test_v025_to_v026_migration_drops_the_indexes(tmp_path):
    """A v25 database still carrying the indexes migrates forward, loses
    them, and keeps its tracks."""
    db_path = str(tmp_path / "v25.db")
    with MigrationManager(db_path) as manager:
        assert manager.initialize_fresh_database()
        with manager.engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX idx_tracks_fingerprint_status "
                "ON tracks(fingerprint_status)"))
            conn.execute(text(
                "CREATE INDEX idx_tracks_fingerprint_queue "
                "ON tracks(fingerprint_status, created_at)"))
            conn.execute(text(
                "CREATE INDEX idx_tracks_fingerprint_computed_at "
                "ON tracks(fingerprint_computed_at DESC)"))
            conn.execute(text(
                "INSERT INTO tracks (title, filepath, filepath_key, skip_count, "
                "play_count, favorite) "
                "VALUES ('t', '/a/t.wav', '/a/t.wav', 0, 0, 0)"))
            conn.execute(text("UPDATE schema_version SET version = 25"))
        assert DROPPED_INDEXES <= _track_index_names(manager.engine)

    with MigrationManager(db_path) as manager:
        assert manager.get_current_version() == 25
        assert manager.migrate_to_latest()
        assert not DROPPED_INDEXES & _track_index_names(manager.engine)
        with manager.engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM tracks")).scalar() == 1


def test_library_stats_table_is_dropped_and_model_gone(tmp_path):
    from auralis.library import models

    assert not hasattr(models, 'LibraryStats')
    db_path = str(tmp_path / "stats.db")
    with MigrationManager(db_path) as manager:
        assert manager.initialize_fresh_database()
        with manager.engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE library_stats (id INTEGER PRIMARY KEY)"))
            conn.execute(text("UPDATE schema_version SET version = 25"))
        assert manager.migrate_to_latest()
        with manager.engine.connect() as conn:
            names = {row[0] for row in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"))}
        assert 'library_stats' not in names


def test_migration_is_idempotent(tmp_path):
    with MigrationManager(str(tmp_path / "again.db")) as manager:
        assert manager.initialize_fresh_database()
        with manager.engine.begin() as conn:
            conn.execute(text("UPDATE schema_version SET version = 25"))
        assert manager.migrate_to_latest()
        assert not DROPPED_INDEXES & _track_index_names(manager.engine)
