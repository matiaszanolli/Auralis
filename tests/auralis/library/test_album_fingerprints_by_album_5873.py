"""Album fingerprints come from one Track/TrackFingerprint join (#5873).

The album fingerprint route loaded the full album detail (every track with
its genres, artists and album) only to collect track ids, once per album tile
in the grid.
"""

from sqlalchemy import event

from auralis.analysis.fingerprint.schema import DIMENSION_SCHEMA


def _track(library_database, path, album):
    info = {
        "title": path, "artists": ["A"], "album": album, "filepath": f"/t/{path}.flac",
        "duration": 10.0, "filesize": 1000, "sample_rate": 44100, "channels": 2,
        "format": "FLAC", "file_mtime": 1_000_000.0,
    }
    track = library_database.tracks.add(info)
    assert track is not None
    return track


def test_one_join_groups_current_fingerprints_by_album(library_database):
    one = _track(library_database, "one", "B")
    two = _track(library_database, "two", "B")
    loose = _track(library_database, "three", "C")
    for track, lufs in ((one, -10.0), (two, -14.0)):
        fingerprint = {name: 0.5 for name in DIMENSION_SCHEMA} | {"lufs": lufs}
        assert library_database.fingerprints.upsert(track.id, fingerprint) is not None

    statements: list[str] = []
    engine = library_database.engine

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        by_album = library_database.fingerprints.get_by_album_ids([one.album_id, loose.album_id])
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert len(statements) == 1
    assert set(by_album) == {one.album_id}  # album C has no fingerprinted track
    assert sorted(fp.lufs for fp in by_album[one.album_id]) == [-14.0, -10.0]


def test_no_ids_issue_no_query(library_database):
    assert library_database.fingerprints.get_by_album_ids([]) == {}
