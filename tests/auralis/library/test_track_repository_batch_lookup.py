"""Tests for bounded batched TrackRepository lookups (#4690)."""

from sqlalchemy import event

import auralis.library.repositories.track_repository as track_repository_module


def _add_tracks(track_repository, count: int):
    tracks = []
    for index in range(count):
        track = track_repository.add({
            'title': f'Track {index}',
            'filepath': f'/music/batch_{index}.flac',
            'sample_rate': 44_100,
            'channels': 2,
            'format': 'FLAC',
        })
        assert track is not None
        tracks.append(track)
    return tracks


def test_batch_lookups_chunk_in_clauses_and_return_partial_maps(
    track_repository, session_factory, monkeypatch
):
    tracks = _add_tracks(track_repository, 5)
    engine = session_factory.kw['bind']
    query_counts = {'id': 0, 'filepath': 0}

    def count_main_queries(_conn, _cursor, statement, _parameters, _context, _many):
        if 'WHERE tracks.id IN' in statement:
            query_counts['id'] += 1
        if 'WHERE tracks.filepath IN' in statement:
            query_counts['filepath'] += 1

    monkeypatch.setattr(track_repository_module, '_SQLITE_IN_BATCH_SIZE', 2)
    event.listen(engine, 'before_cursor_execute', count_main_queries)
    try:
        by_path = track_repository.get_by_paths(
            [track.filepath for track in tracks] + ['/music/missing.flac']
        )
        by_id = track_repository.get_by_ids(
            [track.id for track in tracks] + [tracks[0].id, 999_999]
        )
    finally:
        event.remove(engine, 'before_cursor_execute', count_main_queries)

    assert set(by_path) == {track.filepath for track in tracks}
    assert set(by_id) == {track.id for track in tracks}
    assert query_counts == {'id': 3, 'filepath': 3}
    assert all(track.artists == [] for track in by_path.values())
