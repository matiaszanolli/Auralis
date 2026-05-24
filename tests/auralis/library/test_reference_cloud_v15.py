"""
Migration v014 → v015 + reference-cloud repository methods.

Pins the contract for the schema v15 changes that enable the mastering
reference cloud:
  - track_fingerprints.is_reference column exists, defaults to False
  - FingerprintRepository.get_reference_cloud() filters correctly
  - clear_all_reference_flags() and set_reference_flags() do bulk updates
  - migrate_to_latest() on a fresh DB lands at v15 (no errors)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from auralis.__version__ import __db_schema_version__
from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Track, TrackFingerprint
from auralis.library.repositories.fingerprint_repository import FingerprintRepository


@pytest.fixture
def fresh_db_with_session():
    """Create a fresh schema-v15 SQLite database and yield a session factory."""
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "library.db"
    manager = MigrationManager(str(db_path))
    assert manager.migrate_to_latest()
    assert manager.get_current_version() == __db_schema_version__

    engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
    session_factory = sessionmaker(bind=engine)
    yield db_path, session_factory
    engine.dispose()
    manager.close()


def _seed_track_and_fp(session, track_id: int, *, is_reference: bool = False, **fp_overrides):
    """Insert a track + fingerprint pair for repository tests."""
    track = Track(
        id=track_id,
        filepath=f"/tmp/track_{track_id}.flac",
        title=f"Track {track_id}",
        duration=120.0,
        sample_rate=44100,
        channels=2,
        format="FLAC",
    )
    session.add(track)
    fp_data = dict(
        track_id=track_id,
        sub_bass_pct=0.05, bass_pct=0.20, low_mid_pct=0.15, mid_pct=0.25,
        upper_mid_pct=0.15, presence_pct=0.10, air_pct=0.10,
        lufs=-14.0, crest_db=12.0, bass_mid_ratio=0.0,
        tempo_bpm=120.0, rhythm_stability=0.7, transient_density=0.4, silence_ratio=0.02,
        spectral_centroid=0.4, spectral_rolloff=0.5, spectral_flatness=0.2,
        harmonic_ratio=0.7, pitch_stability=0.7, chroma_energy=0.6,
        dynamic_range_variation=0.3, loudness_variation_std=1.5, peak_consistency=0.7,
        stereo_width=0.4, phase_correlation=0.8,
        fingerprint_version=1,
        is_reference=is_reference,
    )
    fp_data.update(fp_overrides)
    fp = TrackFingerprint(**fp_data)
    session.add(fp)
    session.commit()


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------

def test_fresh_db_lands_at_v15(fresh_db_with_session):
    """A fresh migrate_to_latest() must reach schema v15 (or later)."""
    _db_path, session_factory = fresh_db_with_session
    assert __db_schema_version__ >= 15
    with session_factory() as session:
        result = session.execute(
            text("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        ).scalar_one()
    assert result >= 15


def test_is_reference_column_exists_with_default_false(fresh_db_with_session):
    """Newly inserted fingerprints must default is_reference to False."""
    _db_path, session_factory = fresh_db_with_session
    with session_factory() as session:
        _seed_track_and_fp(session, track_id=1)
        fp = session.execute(
            text("SELECT is_reference FROM track_fingerprints WHERE track_id = 1")
        ).scalar_one()
    # SQLite stores BOOLEAN as INTEGER 0/1; both equal False in Python
    assert not fp


def test_is_reference_index_was_created(fresh_db_with_session):
    """The partial index on is_reference must exist (mastering hot-path)."""
    _db_path, session_factory = fresh_db_with_session
    with session_factory() as session:
        indexes = session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='track_fingerprints'"
        )).scalars().all()
    assert 'ix_fingerprints_is_reference' in set(indexes)


# ---------------------------------------------------------------------------
# Repository methods
# ---------------------------------------------------------------------------

def test_get_reference_cloud_returns_only_flagged(fresh_db_with_session):
    _db_path, session_factory = fresh_db_with_session
    with session_factory() as session:
        _seed_track_and_fp(session, 1, is_reference=True)
        _seed_track_and_fp(session, 2, is_reference=False)
        _seed_track_and_fp(session, 3, is_reference=True)

    repo = FingerprintRepository(session_factory)
    cloud = repo.get_reference_cloud()
    track_ids = sorted(fp.track_id for fp in cloud)
    assert track_ids == [1, 3]


def test_get_reference_cloud_empty_when_none_flagged(fresh_db_with_session):
    _db_path, session_factory = fresh_db_with_session
    with session_factory() as session:
        _seed_track_and_fp(session, 1, is_reference=False)
        _seed_track_and_fp(session, 2, is_reference=False)

    repo = FingerprintRepository(session_factory)
    assert repo.get_reference_cloud() == []


def test_set_reference_flags_updates_existing_rows(fresh_db_with_session):
    _db_path, session_factory = fresh_db_with_session
    with session_factory() as session:
        _seed_track_and_fp(session, 1, is_reference=False)
        _seed_track_and_fp(session, 2, is_reference=False)
        _seed_track_and_fp(session, 3, is_reference=True)

    repo = FingerprintRepository(session_factory)
    # Flip 1 → True, 2 stays False, 3 → False
    updated = repo.set_reference_flags({1: True, 2: False, 3: False})
    # Only 1 and 3 actually changed (2 was already False)
    assert updated == 2

    cloud = repo.get_reference_cloud()
    assert sorted(fp.track_id for fp in cloud) == [1]


def test_clear_all_reference_flags(fresh_db_with_session):
    _db_path, session_factory = fresh_db_with_session
    with session_factory() as session:
        _seed_track_and_fp(session, 1, is_reference=True)
        _seed_track_and_fp(session, 2, is_reference=True)
        _seed_track_and_fp(session, 3, is_reference=False)

    repo = FingerprintRepository(session_factory)
    cleared = repo.clear_all_reference_flags()
    assert cleared == 2
    assert repo.get_reference_cloud() == []


def test_set_reference_flags_ignores_missing_track_ids(fresh_db_with_session):
    """If a track_id has no fingerprint, the flag request is silently ignored."""
    _db_path, session_factory = fresh_db_with_session
    with session_factory() as session:
        _seed_track_and_fp(session, 1, is_reference=False)

    repo = FingerprintRepository(session_factory)
    updated = repo.set_reference_flags({1: True, 99999: True})
    assert updated == 1  # only track 1 actually exists
    cloud = repo.get_reference_cloud()
    assert [fp.track_id for fp in cloud] == [1]
