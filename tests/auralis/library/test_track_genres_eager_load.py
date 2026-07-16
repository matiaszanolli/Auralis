"""
Regression: every track read path eager-loads Track.genres (#4500)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every read path except get_by_artist omitted selectinload(Track.genres) and
then expunge()d the Track. Because Track.genres was lazy, to_dict()'s genre
access raised DetachedInstanceError, which was swallowed and returned
genres: [] — silent genre data loss on list/single-fetch/search/favorites/
recent/popular/genre-filter queries. The eager-load option is now centralised so
every path loads genres.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def seed(track_repository):
    track = track_repository.add({
        'title': 'GenreSeed',
        'filepath': '/audio/genreseed.wav',
        'duration': 10.0,
        'sample_rate': 44100,
        'channels': 2,
        'format': 'WAV',
        'artists': ['Genre Artist'],
        'genres': ['TestRock'],
    })
    assert track is not None
    return track


def _genres(track):
    return track.to_dict()['genres']


def test_get_by_id_returns_genres(track_repository, seed):
    t = track_repository.get_by_id(seed.id)
    assert t is not None
    assert 'TestRock' in _genres(t)


def test_get_all_returns_genres(track_repository, seed):
    tracks, _ = track_repository.get_all()
    t = next(x for x in tracks if x.id == seed.id)
    assert 'TestRock' in _genres(t)


def test_search_returns_genres(track_repository, seed):
    tracks, _ = track_repository.search('GenreSeed')
    t = next(x for x in tracks if x.id == seed.id)
    assert 'TestRock' in _genres(t)


def test_get_by_genre_returns_genres(track_repository, seed):
    tracks = track_repository.get_by_genre('TestRock')
    assert tracks, "genre-filtered query returned nothing"
    assert 'TestRock' in _genres(tracks[0])


def test_detached_genre_access_does_not_raise(track_repository, seed):
    """The returned Track is expunged; accessing .genres must not raise
    DetachedInstanceError now that it is eager-loaded."""
    t = track_repository.get_by_id(seed.id)
    assert t is not None
    names = [g.name for g in t.genres]  # would raise on the old lazy path
    assert 'TestRock' in names
