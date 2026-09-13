"""Regression test: update_metadata()'s returned Track must be safe to
serialize outside its session (#5247).

update_metadata() used to session.refresh() the track and expunge() it
without ever eager-loading (or re-querying with) album/artists/genres.
refresh() expires an instance without re-applying query-level load
options (CLAUDE.md's own documented rule), so those relationships stayed
unloaded — any access after expunge() raised DetachedInstanceError, and
Track.to_dict()'s _safe_scalar/_safe_collection guards silently degraded
to None/[] with a logged warning rather than crashing, masking the gap.
update()/update_by_filepath() in the same file already re-query with
_track_eager_options() post-commit before detaching; update_metadata()
now matches that pattern.
"""


def _add_track(track_repository, filepath="/music/update_metadata_detached_test.flac"):
    track = track_repository.add({
        'title': 'Update Metadata Detached Test',
        'filepath': filepath,
        'sample_rate': 44_100,
        'channels': 2,
        'format': 'FLAC',
        'artists': ['Detached Test Artist'],
        'album': 'Detached Test Album',
        'genres': ['Detached Test Genre'],
    })
    assert track is not None
    return track


def test_update_metadata_result_relationships_accessible_after_detach(track_repository):
    track = _add_track(track_repository)

    updated = track_repository.update_metadata(track.id, title='New Title')

    assert updated is not None
    assert updated.title == 'New Title'

    # Must not raise DetachedInstanceError, and must reflect the real,
    # already-populated relationships rather than silently degrading.
    assert updated.album is not None
    assert updated.album.title == 'Detached Test Album'
    assert [a.name for a in updated.artists] == ['Detached Test Artist']
    assert [g.name for g in updated.genres] == ['Detached Test Genre']


def test_update_metadata_result_to_dict_reflects_relationships(track_repository):
    track = _add_track(track_repository)

    updated = track_repository.update_metadata(track.id, title='Another Title')

    data = updated.to_dict()
    assert data['album'] == 'Detached Test Album'
    assert data['artists'] == ['Detached Test Artist']
    assert data['genres'] == ['Detached Test Genre']
