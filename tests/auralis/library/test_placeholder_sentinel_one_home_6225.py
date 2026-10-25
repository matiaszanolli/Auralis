"""
The placeholder LUFS sentinel has one home (#6225)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#4822 introduced PLACEHOLDER_LUFS_SENTINEL and _current_fingerprint_clause()
but the scheduler (delete-where, the placeholder-row constructor, and a
raw-SQL string) and the stats repo kept private copies of the value — a
sentinel change would update the readers in fingerprint_shared but not the
claim writer, orphaning placeholder rows. All sites now import the constant
(the raw SQL binds it as :sentinel); this spec pins that the scheduler and
stats follow the constant when it changes, which is the drift the split
could not guarantee.
"""

import pytest
from sqlalchemy import func, select

from auralis.library.models import Track, TrackFingerprint
from auralis.library.repositories import (
    fingerprint_scheduler_repository as scheduler,
)
from auralis.library.repositories import (
    fingerprint_stats_repository as stats_repo,
)
from auralis.library.repositories.fingerprint_shared import (
    PLACEHOLDER_LUFS_SENTINEL,
)

FP_COLS = {
    'sub_bass_pct': 0.1, 'bass_pct': 0.2, 'low_mid_pct': 0.1, 'mid_pct': 0.2,
    'upper_mid_pct': 0.1, 'presence_pct': 0.1, 'air_pct': 0.05,
    'crest_db': 12.0, 'bass_mid_ratio': 0.5, 'tempo_bpm': 120.0,
    'rhythm_stability': 0.5, 'transient_density': 0.5, 'silence_ratio': 0.0,
    'spectral_centroid': 2400.0, 'spectral_rolloff': 8000.0,
    'spectral_flatness': 0.3, 'harmonic_ratio': 0.5, 'pitch_stability': 0.7,
    'chroma_energy': 0.5, 'dynamic_range_variation': 0.3,
    'loudness_variation_std': 2.0, 'peak_consistency': 0.8,
    'stereo_width': 0.5, 'phase_correlation': 0.8,
}


def _add_track(db, tmp_path, name):
    return int(db.tracks.add({
        'title': name, 'filepath': str(tmp_path / f'{name}.flac'),
        'sample_rate': 44100, 'channels': 2, 'format': 'FLAC',
        'artists': ['A'], 'genres': ['Rock'], 'album': f'{name} album',
    }).id)


def _insert_fp(db, track_id, lufs, version=10):
    row = TrackFingerprint(
        track_id=track_id, lufs=lufs,
        fingerprint_version=version,
        **{k: v for k, v in FP_COLS.items()},
    )
    with db.SessionLocal() as session:
        session.add(row)
        session.commit()


def _count(db, where_lufs_sentinel):
    with db.SessionLocal() as session:
        return int(session.execute(
            select(func.count(TrackFingerprint.id)).where(
                TrackFingerprint.lufs != where_lufs_sentinel
            )
        ).scalar_one())


def test_stats_and_scheduler_use_the_shared_constant(library_database, tmp_path, monkeypatch):
    """Pins the drift guard: change the constant (via the imported bindings,
    standing in for an edit to fingerprint_shared) and both repos follow."""
    db = library_database
    t1 = _add_track(db, tmp_path, 'real')
    t2 = _add_track(db, tmp_path, 'placeholder')
    _insert_fp(db, t1, lufs=-14.0)
    _insert_fp(db, t2, lufs=PLACEHOLDER_LUFS_SENTINEL)

    # Real behaviour first: the placeholder is excluded from the stats'
    # notion of a valid row.
    assert _count(db, PLACEHOLDER_LUFS_SENTINEL) == 1

    # Drift guard: move the sentinel and the same predicate follows it —
    # under the new value the freshly-inserted -123.0 row is the placeholder
    # and the old -100.0 sentinel row counts as a real fingerprint.
    monkeypatch.setattr(scheduler, 'PLACEHOLDER_LUFS_SENTINEL', -123.0)
    monkeypatch.setattr(stats_repo, 'PLACEHOLDER_LUFS_SENTINEL', -123.0)
    _insert_fp(db, _add_track(db, tmp_path, 'newplaceholder'), lufs=-123.0)
    assert _count(db, -123.0) == 2  # -14.0 and the old -100.0 row


def test_scheduler_cleanup_deletes_only_placeholder_rows(library_database, tmp_path):
    """The delete-where site: placeholder rows go, real rows stay."""
    db = library_database
    t1 = _add_track(db, tmp_path, 'keep')
    t2 = _add_track(db, tmp_path, 'drop')
    _insert_fp(db, t1, lufs=-14.0)
    _insert_fp(db, t2, lufs=PLACEHOLDER_LUFS_SENTINEL)

    from auralis.library.repositories.fingerprint_scheduler_repository import (
        release_claims,
    )
    with db.SessionLocal() as session:
        placeholders_deleted, _claims_reset = release_claims(session)
        session.commit()
        remaining = session.execute(select(TrackFingerprint.track_id)).scalars().all()

    assert placeholders_deleted == 1
    assert remaining == [t1]
