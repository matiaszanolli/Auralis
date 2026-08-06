"""
Regression: to_dict() on a detached instance never raises (#4641)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`Album`, `Artist`, `Genre` and `Playlist` all compute `track_count` from
`len(self.tracks)`, and every repository `expunge()`es the instance it
returns. `GenreRepository` eager-loaded nothing at all, so a genre fetched
through any of its read paths raised `DetachedInstanceError` from
`to_dict()` — unguarded, unlike `Track.to_dict()` (#4500).

Two layers are covered here:

1. The repositories eager-load the relationship, so `track_count` is
   *accurate* on a detached instance (the primary fix).
2. `to_dict()` degrades instead of raising when an eager-load is missing
   (the backstop) — asserted directly against a hand-detached instance.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from auralis.library.models import Album, Artist, Genre, Playlist, Track


# ---------------------------------------------------------------------------
# Layer 1 — repository read paths return usable detached instances
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_genre(track_repository, genre_repository):
    """A genre with two tracks attached, created through the repositories."""
    for i in range(2):
        track = track_repository.add({
            'title': f'DetachSeed {i}',
            'filepath': f'/audio/detachseed{i}.wav',
            'duration': 12.5,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': ['Detach Artist'],
            'genres': ['DetachGenre'],
            'album': 'Detach Album',
        })
        assert track is not None

    genre = genre_repository.get_by_name('DetachGenre')
    assert genre is not None, "seed genre was not created"
    return genre


def _to_dict_without_backstop(instance, caplog):
    """
    Serialise, asserting the `_safe_collection` backstop never fired.

    `to_dict()` degrades to `track_count: 0` on an unloaded relationship, so a
    plain equality check would also pass for a genre with zero tracks against
    a repository that eager-loads nothing. The WARNING the backstop emits is
    what distinguishes "eager-loaded and correct" from "swallowed and
    coincidentally right" — which is exactly how #4500 stayed hidden.
    """
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger='auralis.library.models.core'):
        result = instance.to_dict()
    assert not caplog.records, (
        'to_dict() fell back to the detached-instance guard; the repository '
        f'read path is missing an eager load: {[r.message for r in caplog.records]}'
    )
    return result


def test_get_by_id_track_count(genre_repository, seeded_genre, caplog):
    genre = genre_repository.get_by_id(seeded_genre.id)
    assert genre is not None
    assert _to_dict_without_backstop(genre, caplog)['track_count'] == 2


def test_get_by_name_track_count(genre_repository, seeded_genre, caplog):
    genre = genre_repository.get_by_name('DetachGenre')
    assert genre is not None
    assert _to_dict_without_backstop(genre, caplog)['track_count'] == 2


def test_get_all_track_count(genre_repository, seeded_genre, caplog):
    genres, _total = genre_repository.get_all()
    genre = next(g for g in genres if g.id == seeded_genre.id)
    assert _to_dict_without_backstop(genre, caplog)['track_count'] == 2


def test_search_track_count(genre_repository, seeded_genre, caplog):
    genres, _total = genre_repository.search('DetachGenre')
    genre = next(g for g in genres if g.id == seeded_genre.id)
    assert _to_dict_without_backstop(genre, caplog)['track_count'] == 2


def test_create_and_update_track_count(genre_repository, caplog):
    created = genre_repository.create('FreshDetachGenre', preferred_profile='warm')
    assert _to_dict_without_backstop(created, caplog)['track_count'] == 0

    updated = genre_repository.update(created.id, preferred_profile='bright')
    assert updated is not None
    result = _to_dict_without_backstop(updated, caplog)
    assert result['preferred_profile'] == 'bright'
    assert result['track_count'] == 0


@pytest.fixture
def seeded_album(track_repository, album_repository):
    """An album with three tracks of known durations, created through the
    repositories (#4777)."""
    for i, duration in enumerate((100.0, 150.0, 50.0)):
        track = track_repository.add({
            'title': f'AlbumDetachSeed {i}',
            'filepath': f'/audio/albumdetachseed{i}.wav',
            'duration': duration,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': ['Album Detach Artist'],
            'album': 'Album Detach Seed Album',
        })
        assert track is not None

    album = album_repository.get_by_title('Album Detach Seed Album')
    assert album is not None, "seed album was not created"
    return album


def test_get_all_track_count_and_duration_without_loading_tracks(
    album_repository, seeded_album, caplog
):
    """get_all()'s track_count/total_duration come from track_count_expr/
    total_duration_expr (#4777) — to_dict() must not fall back to the
    _safe_collection backstop (which would mean `tracks` was touched, the
    exact N+1 this fix removes)."""
    albums, _total = album_repository.get_all(limit=50)
    album = next(a for a in albums if a.id == seeded_album.id)
    result = _to_dict_without_backstop(album, caplog)
    assert result['track_count'] == 3
    assert result['total_duration'] == 300.0


def test_get_recent_track_count_and_duration_without_loading_tracks(
    album_repository, seeded_album, caplog
):
    albums = album_repository.get_recent(limit=50)
    album = next(a for a in albums if a.id == seeded_album.id)
    result = _to_dict_without_backstop(album, caplog)
    assert result['track_count'] == 3
    assert result['total_duration'] == 300.0


def test_search_track_count_and_duration_without_loading_tracks(
    album_repository, seeded_album, caplog
):
    albums, _total = album_repository.search('Album Detach Seed Album')
    album = next(a for a in albums if a.id == seeded_album.id)
    result = _to_dict_without_backstop(album, caplog)
    assert result['track_count'] == 3
    assert result['total_duration'] == 300.0


def test_album_get_all_is_not_n_plus_one(album_repository, track_repository, session_factory):
    """track_count_expr/total_duration_expr are correlated scalar subqueries
    on the main album SELECT — not a per-album Track fetch (#4777)."""
    for i in range(6):
        track_repository.add({
            'title': f'NPlusOneAlbumTrack{i}',
            'filepath': f'/audio/nplusonealbumtrack{i}.wav',
            'duration': 30.0,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': ['NPlusOne Album Artist'],
            'album': f'NPlusOneAlbum{i}',
        })

    statements: list[str] = []
    from sqlalchemy import event

    session = session_factory()
    engine = session.get_bind()
    session.close()

    def _record(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(engine, 'before_cursor_execute', _record)
    try:
        albums, _total = album_repository.get_all(limit=50)
    finally:
        event.remove(engine, 'before_cursor_execute', _record)

    # count + album SELECT (artist joinedload + the two scalar subqueries are
    # part of that single SELECT's column list, not separate statements).
    assert len(statements) <= 2, (
        f"expected a bounded query count, got {len(statements)}:\n"
        + "\n".join(statements)
    )


def test_album_update_artwork_path_survives_detach(album_repository, track_repository, caplog):
    """Sibling gap: the one AlbumRepository path that did not eager-load."""
    track = track_repository.add({
        'title': 'ArtworkDetach',
        'filepath': '/audio/artworkdetach.wav',
        'duration': 42.0,
        'sample_rate': 44100,
        'channels': 2,
        'format': 'WAV',
        'artists': ['Artwork Artist'],
        'album': 'Artwork Album',
    })
    assert track is not None and track.album_id is not None

    album = album_repository.update_artwork_path(track.album_id, '/tmp/art.jpg')
    assert album is not None
    result = _to_dict_without_backstop(album, caplog)
    assert result['track_count'] == 1
    assert result['artist'] == 'Artwork Artist'


def test_get_all_is_not_n_plus_one(genre_repository, session_factory):
    """selectinload issues a bounded number of queries, not one per genre."""
    for i in range(6):
        genre_repository.create(f'NPlusOneGenre{i}')

    statements: list[str] = []
    from sqlalchemy import event

    session = session_factory()
    engine = session.get_bind()
    session.close()

    def _record(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(engine, 'before_cursor_execute', _record)
    try:
        genres, _total = genre_repository.get_all(limit=50)
    finally:
        event.remove(engine, 'before_cursor_execute', _record)

    assert len(genres) >= 6
    # count + genre SELECT + one IN-clause SELECT for the tracks collection.
    assert len(statements) <= 4, (
        f"expected a bounded query count, got {len(statements)}:\n"
        + "\n".join(statements)
    )


# ---------------------------------------------------------------------------
# Layer 2 — the to_dict() backstop, across all four models
# ---------------------------------------------------------------------------

@pytest.fixture
def unloaded_rows(session_factory):
    """
    Insert one row of each model — each with a real related track — then hand
    back genuinely detached instances loaded with **no** eager-load options.
    Any relationship access on these raises DetachedInstanceError, which is
    exactly the state a repository missing a `selectinload` would produce.
    """
    from sqlalchemy import select

    session = session_factory()
    try:
        artist = Artist(name='Backstop Artist')
        album = Album(title='Backstop Album', artist=artist)
        genre = Genre(name='Backstop Genre')
        playlist = Playlist(name='Backstop Playlist')
        track = Track(
            title='Backstop Track',
            filepath='/audio/backstop.wav',
            duration=30.0,
        )
        track.album = album
        track.artists.append(artist)
        track.genres.append(genre)
        playlist.tracks.append(track)
        session.add_all([artist, album, genre, playlist, track])
        session.commit()
        ids = {
            'album': album.id,
            'artist': artist.id,
            'genre': genre.id,
            'playlist': playlist.id,
        }
    finally:
        session.close()

    session = session_factory()
    try:
        detached: dict[str, Any] = {}
        for key, model in (
            ('album', Album), ('artist', Artist),
            ('genre', Genre), ('playlist', Playlist),
        ):
            obj = session.execute(
                select(model).where(model.id == ids[key])
            ).scalars().one()
            session.expunge(obj)
            detached[key] = obj
        return detached
    finally:
        session.close()


@pytest.mark.parametrize(
    'key', ['album', 'artist', 'genre', 'playlist']
)
def test_to_dict_degrades_on_unloaded_relationship(key, unloaded_rows):
    """
    A relationship that cannot be loaded degrades to an empty collection
    rather than propagating DetachedInstanceError to the caller.
    """
    result = unloaded_rows[key].to_dict()  # must not raise

    # Degraded, not accurate — the repositories are what make it accurate.
    assert result['track_count'] == 0
    if key == 'artist':
        assert result['album_count'] == 0
    if key == 'album':
        assert result['artist'] is None
        assert result['total_duration'] == 0
    if key == 'playlist':
        assert result['total_duration'] == 0
    # Scalar columns are unaffected by the guard.
    assert result['id'] is not None
