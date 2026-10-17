"""
Regression tests for #5530 — fresh-install fingerprint writes.

Root cause: ``TrackFingerprint.is_reference`` / ``.reference_weight`` (and
``.fingerprint_version``) were declared ``nullable=False`` with Python-side
``default=`` only, which SQLAlchemy applies at ORM-flush time and never emits
as DDL. Migrated databases got real SQL defaults from the ALTER TABLE steps
(v014->v015, v016->v017), but a fresh install is built purely by
``Base.metadata.create_all`` — so its ``track_fingerprints`` had NOT NULL
columns with no DEFAULT, and the raw ``INSERT`` in ``upsert()`` /
``store_fingerprint()`` (which omitted those columns) always raised
``IntegrityError``, was swallowed, and returned ``None``: no fingerprint was
ever persisted on a fresh install.

Fix: server_default on the model columns (matching the migration ALTERs
exactly) plus the columns listed INSERT-only in both raw statements.

These tests run against the conftest ``session_factory``, which builds its
database with ``Base.metadata.create_all`` — i.e. the fresh-install schema.
"""

from __future__ import annotations

import re

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


@pytest.fixture
def track_id(session_factory) -> int:
    """Create a Track row so the FK constraint is satisfied."""
    with session_factory() as s:
        track = Track(title="Fresh Install Track", filepath="/tmp/fresh.flac")
        s.add(track)
        s.commit()
        return int(track.id)


def _fp_row(session_factory, track_id: int) -> dict:
    with session_factory() as s:
        row = s.execute(
            text(
                "SELECT track_id, is_reference, reference_weight, fingerprint_version "
                "FROM track_fingerprints WHERE track_id = :tid"
            ),
            {"tid": track_id},
        ).fetchone()
    assert row is not None, "no track_fingerprints row was created"
    return {"track_id": row[0], "is_reference": row[1], "reference_weight": row[2], "version": row[3]}


def test_upsert_on_fresh_install_succeeds(fingerprint_repository, session_factory, track_id):
    """The production call from fingerprint_extractor.py on a fresh DB."""
    result = fingerprint_repository.upsert(track_id=track_id, fingerprint_data=_SAMPLE_FP)

    assert result is not None, "upsert() must succeed on a create_all() schema"
    row = _fp_row(session_factory, track_id)
    assert row["is_reference"] in (0, False)
    assert row["reference_weight"] == 0.0
    assert row["version"] >= 1


def test_store_fingerprint_on_fresh_install_succeeds(fingerprint_repository, session_factory, track_id):
    result = fingerprint_repository.store_fingerprint(track_id=track_id, **_SAMPLE_FP)

    assert result is not None, "store_fingerprint() must succeed on a create_all() schema"
    row = _fp_row(session_factory, track_id)
    assert row["is_reference"] in (0, False)
    assert row["reference_weight"] == 0.0


def test_upsert_does_not_clobber_reference_membership(
    fingerprint_repository, session_factory, track_id
):
    """is_reference/reference_weight are INSERT-only: a dimension refresh must
    never reset the reference-cloud membership the seeder set."""
    fingerprint_repository.upsert(track_id=track_id, fingerprint_data=_SAMPLE_FP)

    with session_factory() as s:
        s.execute(
            text("UPDATE track_fingerprints SET is_reference = 1, reference_weight = 0.75 "
                 "WHERE track_id = :tid"),
            {"tid": track_id},
        )
        s.commit()

    fingerprint_repository.upsert(track_id=track_id, fingerprint_data=_SAMPLE_FP)

    row = _fp_row(session_factory, track_id)
    assert row["is_reference"] in (1, True)
    assert row["reference_weight"] == 0.75


def test_fresh_schema_ddl_carries_sql_defaults(session_factory):
    """A fresh create_all() database must emit the same SQL defaults the
    migration ALTER TABLEs give migrated databases (#5530, cf. #5321)."""
    with session_factory() as s:
        ddl = s.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='track_fingerprints'")
        ).fetchone()[0]
        tracks_ddl = s.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='tracks'")
        ).fetchone()[0]

    # SQLAlchemy may parenthesize multi-char literals ("DEFAULT (0.0)").
    def has_default(ddl: str, column: str, literal: str) -> bool:
        return re.search(rf"{column}[^,]*DEFAULT \(?{re.escape(literal)}\)?", ddl) is not None

    assert has_default(ddl, "is_reference", "0")
    assert has_default(ddl, "reference_weight", "0.0")
    assert has_default(ddl, "fingerprint_version", "1")
    assert has_default(tracks_ddl, "play_count", "0")
