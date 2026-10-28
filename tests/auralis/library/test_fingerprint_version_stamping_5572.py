"""Regression tests: every fingerprint writer stamps the algorithm version (#5572)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Reads (get_by_track_id/exists) treat a row as usable only when
`fingerprint_version >= FINGERPRINT_ALGORITHM_VERSION`. Only the extractor
path stamped the version; add()/update()/upsert() left rows at the ORM
default (1), so a freshly computed fingerprint was permanently invisible to
the cache — every play re-decoded and re-computed, and the row stayed stale
forever.

Real tmp-file DB at the current schema version; all 25 dimension columns
required by the model are supplied explicitly.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION, __db_schema_version__
from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Track
from auralis.library.repositories.fingerprint_repository import FingerprintRepository

# The model's 25 NOT-NULL dimension columns.
_DIMENSIONS = {
    'sub_bass_pct': 0.05, 'bass_pct': 0.15, 'low_mid_pct': 0.12,
    'mid_pct': 0.22, 'upper_mid_pct': 0.11, 'presence_pct': 0.11,
    'air_pct': 0.05, 'lufs': -14.0, 'crest_db': 12.0,
    'bass_mid_ratio': 1.2, 'tempo_bpm': 120.0, 'rhythm_stability': 0.7,
    'transient_density': 0.4, 'silence_ratio': 0.02,
    'spectral_centroid': 2200.0, 'spectral_rolloff': 15000.0,
    'spectral_flatness': 0.3, 'harmonic_ratio': 0.6,
    'pitch_stability': 0.8, 'chroma_energy': 0.5,
    'dynamic_range_variation': 0.1, 'loudness_variation_std': 0.2,
    'peak_consistency': 0.9, 'stereo_width': 0.7, 'phase_correlation': 0.9,
}


@pytest.fixture
def repo():
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "library.db"
    manager = MigrationManager(str(db_path))
    assert manager.migrate_to_latest()
    assert manager.get_current_version() == __db_schema_version__

    engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
    session_factory = sessionmaker(bind=engine)

    repo = FingerprintRepository(session_factory)

    # Seed a track (FK target).
    with session_factory() as session:
        session.add(Track(
            id=1,
            filepath="/tmp/track_1.flac",
            title="Track 1",
            duration=120.0,
            sample_rate=44100,
            channels=2,
            format="FLAC",
        ))
        session.commit()

    yield repo

    engine.dispose()
    manager.close()


def test_add_stamps_the_current_version(repo):
    """The issue's repro: add(track_id, dims) stored version 1, after which
    get_by_track_id() returned None and exists() returned False."""
    assert repo.add(1, dict(_DIMENSIONS)) is not None

    row = repo.get_by_track_id(1)
    assert row is not None, "freshly added fingerprint invisible to reads"
    assert row.fingerprint_version == FINGERPRINT_ALGORITHM_VERSION
    assert repo.exists(1) is True


def test_update_promotes_an_old_version_row(repo):
    """A row written by an older algorithm version and rewritten through
    update() must be promoted to the current version (self-healing)."""
    repo.add(1, dict(_DIMENSIONS))

    new_dims = {k: v + 0.05 for k, v in _DIMENSIONS.items()}
    updated = repo.update(1, new_dims)
    assert updated is not None
    assert updated.fingerprint_version == FINGERPRINT_ALGORITHM_VERSION
    assert repo.get_by_track_id(1) is not None


def test_upsert_promotes_an_old_version_row(repo):
    """The FingerprintService path: upsert(track_id, dims) with dimensions
    only must refresh fingerprint_version on the DO UPDATE arm."""
    # Simulate an old-version row directly.
    repo.add(1, dict(_DIMENSIONS))
    with repo._session_scope() as session:
        from auralis.library.models import TrackFingerprint
        row = session.scalars(select(TrackFingerprint).filter_by(track_id=1)).one()
        row.fingerprint_version = FINGERPRINT_ALGORITHM_VERSION - 1
        session.commit()

    assert repo.exists(1) is False  # stale by design

    assert repo.upsert(1, dict(_DIMENSIONS)) is not None
    row = repo.get_by_track_id(1)
    assert row is not None, "upserted fingerprint invisible to reads"
    assert row.fingerprint_version == FINGERPRINT_ALGORITHM_VERSION


def test_upsert_with_expected_filepath_stores_when_the_track_still_matches(repo):
    """#6095: the guarded write is a normal upsert while the id still points at
    the file the fingerprint was computed from."""
    assert repo.upsert(1, dict(_DIMENSIONS), expected_filepath="/tmp/track_1.flac") is not None

    row = repo.get_by_track_id(1)
    assert row is not None
    assert row.lufs == _DIMENSIONS['lufs']


def test_upsert_with_expected_filepath_refuses_a_reused_track_id(repo):
    """#6095: an extraction that outlived a library reset must not attach its
    file's fingerprint to whichever different file a rescan gave the id."""
    assert repo.upsert(1, dict(_DIMENSIONS), expected_filepath="/tmp/the_old_file.flac") is None

    assert repo.get_by_track_id(1) is None
    assert repo.exists(1) is False


def test_upsert_with_expected_filepath_refuses_a_deleted_track(repo):
    assert repo.upsert(999, dict(_DIMENSIONS), expected_filepath="/tmp/track_1.flac") is None


def test_guarded_upsert_still_updates_an_existing_row(repo):
    """The ON CONFLICT arm keeps working through INSERT ... SELECT."""
    repo.add(1, dict(_DIMENSIONS))
    changed = {**_DIMENSIONS, 'lufs': -9.0}

    assert repo.upsert(1, changed, expected_filepath="/tmp/track_1.flac") is not None

    row = repo.get_by_track_id(1)
    assert row is not None and row.lufs == -9.0
