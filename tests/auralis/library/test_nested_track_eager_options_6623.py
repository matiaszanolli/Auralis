"""Album, artist and playlist detail reads load every Track relationship (#6623).

Each detail read hands back a collection of Tracks that a router then
serialises with ``Track.to_dict()``. The eager-load tuples for those nested
Tracks were spelled out by hand in three repositories, so a Track relationship
``to_dict()`` started reading had to be added in four places (#4236, #5961).
They now compose ``nested_track_options``, so there is one place. This walks
``to_dict()`` on the nested Tracks of each detail read and requires that the
``_safe_*`` backstop never fires and that nothing was silently swallowed.
"""

from __future__ import annotations

import logging

import pytest

_TRACKS = [
    {
        'title': f'Nested {i}',
        'filepath': f'/audio/nested6623_{i}.wav',
        'duration': 10.0 + i,
        'sample_rate': 44100,
        'channels': 2,
        'format': 'WAV',
        'artists': ['Nested One', 'Nested Two'],
        'genres': ['NestedGenre'],
        'album': 'Nested Album',
    }
    for i in range(2)
]


@pytest.fixture
def seeded(track_repository):
    tracks = [track_repository.add(dict(t)) for t in _TRACKS]
    assert all(t is not None for t in tracks), "seed tracks were not stored"
    return [t.id for t in tracks]


def _nested_track_dicts(tracks, caplog):
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger='auralis.library.models._helpers'):
        dicts = [t.to_dict() for t in tracks]
    assert not caplog.records, (
        'Track.to_dict() fell back to the detached-instance guard; a nested '
        f'Track relationship is not eager-loaded: {[r.message for r in caplog.records]}'
    )
    return dicts


def _assert_every_relationship_arrived(dicts):
    assert len(dicts) == 2
    for d in dicts:
        assert sorted(d['artists']) == ['Nested One', 'Nested Two']
        assert d['genres'] == ['NestedGenre']
        assert d['album'] == 'Nested Album'


def test_album_detail_tracks(seeded, track_repository, album_repository, caplog):
    album_id = track_repository.get_by_id(seeded[0]).album_id
    album = album_repository.get_by_id(album_id)
    _assert_every_relationship_arrived(_nested_track_dicts(album.tracks, caplog))


def test_artist_detail_tracks(seeded, artist_repository, caplog):
    artist = artist_repository.get_by_name('Nested One')
    _assert_every_relationship_arrived(_nested_track_dicts(artist.tracks, caplog))


def test_playlist_detail_tracks(seeded, playlist_repository, caplog):
    playlist = playlist_repository.create('Nested Playlist', track_ids=seeded)
    playlist = playlist_repository.get_by_id(playlist.id)
    _assert_every_relationship_arrived(_nested_track_dicts(playlist.tracks, caplog))
