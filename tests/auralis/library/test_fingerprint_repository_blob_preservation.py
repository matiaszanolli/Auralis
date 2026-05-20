"""
Regression tests for #3467 — upsert() must preserve fingerprint_blob.

Prior bug: `fingerprint_repository.upsert()` used `INSERT OR REPLACE`
listing only `track_id` + the 25 fingerprint dimensions. SQLite's
INSERT OR REPLACE deletes the existing row and inserts a new one, so
any column NOT listed (including the quantized `fingerprint_blob` set
by `store_fingerprint()`) reverted to its default. The similarity
scanner silently lost tracks.

Fix: switched both `upsert()` and `store_fingerprint()` to
`INSERT ... ON CONFLICT (track_id) DO UPDATE SET col=excluded.col`,
which preserves unlisted columns and keeps the `id` PK stable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from auralis.library.models import Track


_SAMPLE_FP: dict = {
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


def _store(fp_repo, track_id: int, fp: dict = _SAMPLE_FP) -> None:
    """Call store_fingerprint with the 25 dims unpacked as kwargs."""
    fp_repo.store_fingerprint(track_id=track_id, **fp)


def _track_row(session_factory, track_id: int) -> dict:
    """Read the raw row for assertions."""
    with session_factory() as s:
        row = s.execute(
            text("SELECT id, track_id, fingerprint_blob, fingerprint_version, lufs "
                 "FROM track_fingerprints WHERE track_id = :tid"),
            {"tid": track_id},
        ).fetchone()
        assert row is not None, f"no row for track_id={track_id}"
        return {
            "id": row[0],
            "track_id": row[1],
            "blob": row[2],
            "version": row[3],
            "lufs": row[4],
        }


@pytest.fixture
def track_id(session_factory) -> int:
    """Create a Track row so the FK constraint is satisfied."""
    with session_factory() as s:
        track = Track(title="Regression Track", filepath="/tmp/regression.flac")
        s.add(track)
        s.commit()
        return int(track.id)


def test_upsert_preserves_fingerprint_blob_after_store(
    fingerprint_repository, session_factory, track_id
):
    """The exact #3467 scenario: store_fingerprint then upsert — the blob
    must NOT be wiped."""
    # Step 1: store_fingerprint populates fingerprint_blob (25-byte quantized).
    _store(fingerprint_repository, track_id)
    initial = _track_row(session_factory, track_id)
    assert initial["blob"] is not None, "store_fingerprint should have written a blob"
    assert len(initial["blob"]) == 25
    blob_before = bytes(initial["blob"])
    id_before = initial["id"]

    # Step 2: upsert updates the 25 dimensions only.
    fp2 = {**_SAMPLE_FP, "lufs": -18.5}  # change one dim to verify update happened
    fingerprint_repository.upsert(track_id=track_id, fingerprint_data=fp2)

    # Step 3: the row must still have the original blob, an unchanged id,
    # and the new lufs value.
    after = _track_row(session_factory, track_id)
    assert after["blob"] == blob_before, \
        "upsert() wiped the fingerprint_blob — #3467 regression"
    assert after["id"] == id_before, \
        "upsert() reset the id PK (INSERT OR REPLACE leak)"
    assert after["lufs"] == pytest.approx(-18.5)


def test_upsert_creates_row_when_track_not_present(
    fingerprint_repository, session_factory, track_id
):
    """First-time upsert (no prior store_fingerprint) still inserts cleanly.
    Blob stays NULL until store_fingerprint runs — that's expected."""
    fingerprint_repository.upsert(track_id=track_id, fingerprint_data=_SAMPLE_FP)
    row = _track_row(session_factory, track_id)
    assert row["track_id"] == track_id
    assert row["lufs"] == pytest.approx(_SAMPLE_FP["lufs"])
    # No store_fingerprint ran, so blob is NULL (this is the documented contract).
    assert row["blob"] is None


def test_store_fingerprint_keeps_id_stable_on_update(
    fingerprint_repository, session_factory, track_id
):
    """store_fingerprint twice on the same track must preserve the id PK
    (ON CONFLICT updates in place; INSERT OR REPLACE would re-insert)."""
    _store(fingerprint_repository, track_id)
    id_first = _track_row(session_factory, track_id)["id"]

    fp2 = {**_SAMPLE_FP, "lufs": -10.0}
    _store(fingerprint_repository, track_id, fp2)
    after = _track_row(session_factory, track_id)

    assert after["id"] == id_first, "store_fingerprint must update in place"
    assert after["lufs"] == pytest.approx(-10.0)
    assert after["blob"] is not None  # blob refreshed by store_fingerprint
