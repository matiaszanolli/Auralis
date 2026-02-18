# -*- coding: utf-8 -*-

"""
Tests for FingerprintRepository configurable db_path (issue #2082)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that raw sqlite3 writes use the db_path passed at construction
instead of the hardcoded ~/.auralis/library.db default.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from auralis.library.repositories.fingerprint_repository import FingerprintRepository


# Minimal schema required by the three raw-sqlite3 methods under test
_CREATE_FINGERPRINTS = """
CREATE TABLE IF NOT EXISTS track_fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER UNIQUE NOT NULL,
    sub_bass_pct REAL, bass_pct REAL, low_mid_pct REAL, mid_pct REAL,
    upper_mid_pct REAL, presence_pct REAL, air_pct REAL,
    lufs REAL, crest_db REAL, bass_mid_ratio REAL,
    tempo_bpm REAL, rhythm_stability REAL, transient_density REAL, silence_ratio REAL,
    spectral_centroid REAL, spectral_rolloff REAL, spectral_flatness REAL,
    harmonic_ratio REAL, pitch_stability REAL, chroma_energy REAL,
    dynamic_range_variation REAL, loudness_variation_std REAL, peak_consistency REAL,
    stereo_width REAL, phase_correlation REAL,
    fingerprint_blob BLOB,
    fingerprint_version INTEGER,
    fingerprint_status TEXT,
    fingerprint_started_at TEXT,
    fingerprint_computed_at TEXT
)
"""

_SAMPLE_FINGERPRINT: dict = {
    'sub_bass_pct': 0.1, 'bass_pct': 0.2, 'low_mid_pct': 0.15,
    'mid_pct': 0.25, 'upper_mid_pct': 0.1, 'presence_pct': 0.1, 'air_pct': 0.1,
    'lufs': -14.0, 'crest_db': 6.0, 'bass_mid_ratio': 0.8,
    'tempo_bpm': 120.0, 'rhythm_stability': 0.9, 'transient_density': 0.5, 'silence_ratio': 0.05,
    'spectral_centroid': 3000.0, 'spectral_rolloff': 8000.0, 'spectral_flatness': 0.3,
    'harmonic_ratio': 0.7, 'pitch_stability': 0.85, 'chroma_energy': 0.6,
    'dynamic_range_variation': 3.0, 'loudness_variation_std': 1.5, 'peak_consistency': 0.9,
    'stereo_width': 0.5, 'phase_correlation': 0.95,
}


@pytest.fixture
def temp_db(tmp_path: Path):
    """Create a temporary sqlite3 database with the required fingerprint table."""
    db = tmp_path / "test_library.db"
    conn = sqlite3.connect(str(db))
    conn.execute(_CREATE_FINGERPRINTS)
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def mock_session_factory():
    """Session factory mock — raw-sqlite3 methods only call expunge_all/close on it."""
    session = MagicMock()
    factory = MagicMock(return_value=session)
    return factory


@pytest.fixture
def repo(temp_db, mock_session_factory):
    return FingerprintRepository(mock_session_factory, db_path=temp_db)


class TestFingerprintRepositoryDbPath:
    """Verify db_path is honoured by all three raw-sqlite3 methods."""

    def test_upsert_writes_to_custom_path(self, repo, temp_db):
        result = repo.upsert(track_id=1, fingerprint_data=_SAMPLE_FINGERPRINT)

        assert result is not None, "upsert should return a TrackFingerprint on success"
        conn = sqlite3.connect(str(temp_db))
        row = conn.execute(
            "SELECT track_id FROM track_fingerprints WHERE track_id = ?", (1,)
        ).fetchone()
        conn.close()
        assert row is not None, "fingerprint should exist in the custom db"
        assert row[0] == 1

    def test_store_fingerprint_writes_to_custom_path(self, repo, temp_db):
        fp = _SAMPLE_FINGERPRINT
        repo.store_fingerprint(
            track_id=2,
            sub_bass_pct=fp['sub_bass_pct'], bass_pct=fp['bass_pct'],
            low_mid_pct=fp['low_mid_pct'], mid_pct=fp['mid_pct'],
            upper_mid_pct=fp['upper_mid_pct'], presence_pct=fp['presence_pct'],
            air_pct=fp['air_pct'], lufs=fp['lufs'], crest_db=fp['crest_db'],
            bass_mid_ratio=fp['bass_mid_ratio'], tempo_bpm=fp['tempo_bpm'],
            rhythm_stability=fp['rhythm_stability'], transient_density=fp['transient_density'],
            silence_ratio=fp['silence_ratio'], spectral_centroid=fp['spectral_centroid'],
            spectral_rolloff=fp['spectral_rolloff'], spectral_flatness=fp['spectral_flatness'],
            harmonic_ratio=fp['harmonic_ratio'], pitch_stability=fp['pitch_stability'],
            chroma_energy=fp['chroma_energy'],
            dynamic_range_variation=fp['dynamic_range_variation'],
            loudness_variation_std=fp['loudness_variation_std'],
            peak_consistency=fp['peak_consistency'],
            stereo_width=fp['stereo_width'], phase_correlation=fp['phase_correlation'],
        )

        conn = sqlite3.connect(str(temp_db))
        row = conn.execute(
            "SELECT track_id, fingerprint_blob FROM track_fingerprints WHERE track_id = ?", (2,)
        ).fetchone()
        conn.close()
        assert row is not None, "fingerprint should exist in the custom db"
        assert row[0] == 2
        assert row[1] is not None, "quantized blob should be stored"

    def test_update_status_writes_to_custom_path(self, repo, temp_db):
        # Seed a row first so UPDATE has something to modify
        conn = sqlite3.connect(str(temp_db))
        conn.execute(
            "INSERT OR REPLACE INTO track_fingerprints (track_id, fingerprint_status) VALUES (?, ?)",
            (3, 'pending'),
        )
        conn.commit()
        conn.close()

        result = repo.update_status(track_id=3, status='failed')

        assert result is True
        conn = sqlite3.connect(str(temp_db))
        row = conn.execute(
            "SELECT fingerprint_status FROM track_fingerprints WHERE track_id = ?", (3,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 'failed'

    def test_default_db_path_fallback(self, mock_session_factory):
        """When no db_path is provided the default ~/.auralis/library.db path is used."""
        repo = FingerprintRepository(mock_session_factory)
        expected = Path.home() / '.auralis' / 'library.db'
        assert repo._db_path == expected

    def test_custom_db_path_does_not_touch_default(self, repo, tmp_path):
        """Writes must NOT reach ~/.auralis/library.db when a custom path is given."""
        default_db = Path.home() / '.auralis' / 'library.db'
        mtime_before = default_db.stat().st_mtime if default_db.exists() else None

        repo.upsert(track_id=99, fingerprint_data=_SAMPLE_FINGERPRINT)

        if default_db.exists() and mtime_before is not None:
            assert default_db.stat().st_mtime == mtime_before, (
                "upsert should not modify the default database when a custom db_path is set"
            )
