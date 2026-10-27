"""
Regression: get-or-create inserts roll back with their session (#5717)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

pysqlite's legacy transaction mode emits no BEGIN before SAVEPOINT, so
``session.begin_nested()`` opened the SQLite transaction itself and the
outermost RELEASE committed it. The artists/genres/albums created by
``_get_or_create_*`` therefore survived a rollback, and a failed ``add()`` left
zero-track orphans. They now use ``INSERT ... ON CONFLICT DO NOTHING`` inside
the session's own transaction.
"""

import threading

from sqlalchemy import event, func, select

from auralis.library.models import Album, Artist, Genre, Track


def _counts(db) -> dict[str, int]:
    with db.SessionLocal() as s:
        return {
            model.__tablename__: s.execute(select(func.count()).select_from(model)).scalar_one()
            for model in (Artist, Genre, Album, Track)
        }


def _info(n: int = 1, **over):
    info = {
        'filepath': f'/tmp/5717_{n}.flac', 'title': f'T{n}', 'duration': 10.0,
        'sample_rate': 44100, 'channels': 2, 'format': 'FLAC',
        'artists': [f'Artist {n}'], 'genres': [f'Genre {n}'], 'album': f'Album {n}',
    }
    info.update(over)
    return info


class TestRollbackTakesTheInsertsBack:
    def test_artists_and_genres_roll_back_with_the_session(self, library_database):
        repo = library_database.tracks
        with library_database.SessionLocal() as session:
            repo._get_or_create_artists(session, ['Ghost Artist'])
            repo._get_or_create_genres(session, ['Ghost Genre'])
            session.rollback()

        assert _counts(library_database) == {'artists': 0, 'genres': 0, 'albums': 0, 'tracks': 0}

    def test_album_rolls_back_with_the_session(self, library_database):
        repo = library_database.tracks
        with library_database.SessionLocal() as session:
            (artist,) = repo._get_or_create_artists(session, ['A'])
            repo._get_or_create_album(session, 'Ghost Album', 1999, artist.id)
            session.rollback()

        assert _counts(library_database)['albums'] == 0

    def test_failed_track_insert_leaves_no_orphans(self, library_database):
        engine = library_database.engine

        def fail_track_insert(conn, cursor, statement, *_a):
            if statement.lstrip().upper().startswith('INSERT INTO TRACKS'):
                raise RuntimeError("simulated track INSERT failure")

        event.listen(engine, 'before_cursor_execute', fail_track_insert)
        try:
            assert library_database.tracks.add(_info(2)) is None
        finally:
            event.remove(engine, 'before_cursor_execute', fail_track_insert)

        assert _counts(library_database) == {'artists': 0, 'genres': 0, 'albums': 0, 'tracks': 0}

    def test_successful_add_still_persists_everything(self, library_database):
        track = library_database.tracks.add(_info(3))

        assert track is not None
        assert _counts(library_database) == {'artists': 1, 'genres': 1, 'albums': 1, 'tracks': 1}


class TestResolveExisting:
    def test_second_lookup_returns_the_same_row(self, library_database):
        repo = library_database.tracks
        with library_database.SessionLocal() as session:
            (a1,) = repo._get_or_create_artists(session, ['Same'])
            (a2,) = repo._get_or_create_artists(session, ['Same'])
            (g1,) = repo._get_or_create_genres(session, ['Rock'])
            (g2,) = repo._get_or_create_genres(session, ['Rock'])
            session.commit()

            assert a1.id == a2.id and g1.id == g2.id

        assert _counts(library_database)['artists'] == 1

    def test_artist_stored_under_an_older_normalisation_is_adopted_and_rekeyed(self, library_database):
        """The unique `name` is taken by a row whose normalized_name differs
        (an older normalisation, #5720): the insert is ignored, the row is
        adopted and re-keyed instead of the lookup coming back empty."""
        with library_database.SessionLocal() as session:
            session.add(Artist(name='Odd', normalized_name='different'))
            session.commit()
            (artist,) = library_database.tracks._get_or_create_artists(session, ['Odd'])
            session.commit()

            assert artist.name == 'Odd' and artist.normalized_name == 'odd'
        assert _counts(library_database)['artists'] == 1

    def test_album_with_vanished_artist_returns_none(self, library_database):
        with library_database.SessionLocal() as session:
            assert library_database.tracks._get_or_create_album(session, 'X', 2000, 99999) is None
            session.rollback()


def test_concurrent_adds_of_the_same_new_artist_and_genre_resolve_to_one_row(library_database):
    """#2594 behaviour preserved: the loser's insert is ignored, not duplicated."""
    start = threading.Barrier(4)
    results: list = []

    def worker(n: int) -> None:
        start.wait(timeout=10)
        results.append(library_database.tracks.add(
            _info(n, artists=['Shared Artist'], genres=['Shared Genre'], album=None)
        ))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(10, 14)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sum(r is not None for r in results) == 4
    counts = _counts(library_database)
    assert (counts['artists'], counts['genres'], counts['tracks']) == (1, 1, 4)
