"""upsert() and store_fingerprint() return the row as stored (#5539).

Both wrote through raw SQL and then returned a transient `TrackFingerprint(track_id=..., **dims)`,
so the object had no id, no timestamps and, for store_fingerprint, no fingerprint_blob, while the
row in the database held all of them.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.library.models import Track

_DIMS: dict = {
    'sub_bass_pct': 0.1, 'bass_pct': 0.2, 'low_mid_pct': 0.15,
    'mid_pct': 0.25, 'upper_mid_pct': 0.1, 'presence_pct': 0.1, 'air_pct': 0.1,
    'lufs': -14.0, 'crest_db': 6.0, 'bass_mid_ratio': 0.8,
    'tempo_bpm': 120.0, 'rhythm_stability': 0.9, 'transient_density': 0.5,
    'silence_ratio': 0.05, 'spectral_centroid': 3000.0, 'spectral_rolloff': 8000.0,
    'spectral_flatness': 0.3, 'harmonic_ratio': 0.7, 'pitch_stability': 0.85,
    'chroma_energy': 0.6, 'dynamic_range_variation': 3.0,
    'loudness_variation_std': 1.5, 'peak_consistency': 0.9,
    'stereo_width': 0.5, 'phase_correlation': 0.95,
}


@pytest.fixture
def track_id(session_factory) -> int:
    with session_factory() as s:
        track = Track(title="Stored Row Track", filepath="/tmp/stored-row.flac")
        s.add(track)
        s.commit()
        return int(track.id)


def _stored(session_factory, track_id: int):
    with session_factory() as s:
        return s.execute(
            text("SELECT id, fingerprint_version, fingerprint_blob FROM track_fingerprints WHERE track_id = :t"),
            {"t": track_id},
        ).one()


def test_upsert_returns_the_stored_row_with_its_id_and_version(fingerprint_repository, session_factory, track_id):
    result = fingerprint_repository.upsert(track_id=track_id, fingerprint_data=_DIMS)

    stored = _stored(session_factory, track_id)
    assert result is not None
    assert result.id == stored.id
    assert result.fingerprint_version == FINGERPRINT_ALGORITHM_VERSION
    assert result.lufs == -14.0


def test_store_fingerprint_returns_the_quantized_blob_it_wrote(fingerprint_repository, session_factory, track_id):
    result = fingerprint_repository.store_fingerprint(track_id=track_id, **_DIMS)

    stored = _stored(session_factory, track_id)
    assert result is not None
    assert result.fingerprint_blob == stored.fingerprint_blob
    assert len(result.fingerprint_blob) == 25
    assert result.fingerprint_version == stored.fingerprint_version == FINGERPRINT_ALGORITHM_VERSION


def test_a_second_upsert_returns_the_same_row_not_a_new_one(fingerprint_repository, track_id):
    first = fingerprint_repository.upsert(track_id=track_id, fingerprint_data=_DIMS)
    second = fingerprint_repository.upsert(track_id=track_id, fingerprint_data={**_DIMS, 'lufs': -9.0})

    assert first is not None and second is not None
    assert second.id == first.id
    assert second.lufs == -9.0


def test_the_returned_row_is_detached_and_readable(fingerprint_repository, track_id):
    result = fingerprint_repository.upsert(track_id=track_id, fingerprint_data=_DIMS)

    assert result is not None
    # Reading columns after the session closed must not raise DetachedInstanceError.
    assert (result.track_id, result.bass_pct, result.created_at is not None) == (track_id, 0.2, True)
