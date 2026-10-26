"""Raw fingerprint upserts write created_at/updated_at (#5753).

`TimestampMixin` only had Python-side defaults, which a raw `INSERT ... ON
CONFLICT` never sees: on a fresh install every upserted fingerprint had NULL
timestamps, so `ORDER BY created_at DESC` (the reference seeder's "most recent
slice") was degenerate.
"""

import pytest
from sqlalchemy import text

from auralis.analysis.fingerprint.schema import DIMENSION_SCHEMA


def _fingerprint() -> dict[str, float]:
    return {name: 0.5 for name in DIMENSION_SCHEMA}


@pytest.fixture
def track_ids(library_database):
    ids = []
    for i in range(3):
        track = library_database.tracks.add({
            "title": f"t{i}", "artists": ["A"], "album": "B", "filepath": f"/t/ts_{i}.flac",
            "duration": 1.0, "filesize": 1, "sample_rate": 44100, "channels": 2,
        })
        ids.append(track.id)
    return ids


def _timestamps(library_database) -> dict[int, tuple[str | None, str | None]]:
    with library_database.SessionLocal() as session:
        rows = session.execute(text("SELECT track_id, created_at, updated_at FROM track_fingerprints")).all()
    return {track_id: (created, updated) for track_id, created, updated in rows}


def test_upsert_stamps_both_timestamps(library_database, track_ids):
    for track_id in track_ids[:2]:
        library_database.fingerprints.upsert(track_id, _fingerprint())

    stamps = _timestamps(library_database)

    assert len(stamps) == 2
    assert all(created and updated for created, updated in stamps.values())


def test_store_fingerprint_stamps_both_timestamps(library_database, track_ids):
    library_database.fingerprints.store_fingerprint(track_ids[0], **_fingerprint())

    created, updated = _timestamps(library_database)[track_ids[0]]

    assert created and updated


def test_a_re_upsert_keeps_created_at_and_refreshes_updated_at(library_database, track_ids):
    track_id = track_ids[0]
    library_database.fingerprints.upsert(track_id, _fingerprint())
    with library_database.SessionLocal() as session:
        session.execute(text(
            "UPDATE track_fingerprints SET created_at = '2020-01-01 00:00:00', "
            "updated_at = '2020-01-01 00:00:00' WHERE track_id = :t"
        ), {"t": track_id})
        session.commit()

    library_database.fingerprints.upsert(track_id, _fingerprint())

    created, updated = _timestamps(library_database)[track_id]
    assert created == '2020-01-01 00:00:00'
    assert updated != '2020-01-01 00:00:00' and updated > created


def test_get_all_order_is_stable_for_rows_written_in_the_same_second(library_database, track_ids):
    for track_id in track_ids:
        library_database.fingerprints.upsert(track_id, _fingerprint())

    first = [fp.track_id for fp in library_database.fingerprints.get_all()]
    second = [fp.track_id for fp in library_database.fingerprints.get_all()]

    assert first == second == sorted(track_ids, reverse=True)
