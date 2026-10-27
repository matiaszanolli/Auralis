"""
Regression: albums resolve per (title, artist) and stay one row under a race (#5595)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``_get_or_create_album`` looked an artist-less track's album up by title alone
(so it could land in another artist's album) and never created one, and the
IntegrityError guard behind its insert could not fire because ``albums`` had no
unique constraint. Albums are now unique per (title, artist_id) -- and per title
for artist-less albums -- and every path resolves through one helper.
"""

import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from sqlalchemy import func, select, text

from auralis.__version__ import __db_schema_version__
from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Album, Track


def _info(n: int, album: str | None = 'Greatest Hits', artists: list[str] | None = None, **over):
    info = {
        'filepath': f'/tmp/5595_{n}.flac', 'title': f'T{n}', 'duration': 10.0,
        'sample_rate': 44100, 'channels': 2, 'format': 'FLAC',
        'artists': artists if artists is not None else [], 'genres': [],
    }
    if album is not None:
        info['album'] = album
    info.update(over)
    return info


def _albums(db) -> list[tuple[int, str, int | None]]:
    with db.SessionLocal() as s:
        return [tuple(r) for r in s.execute(
            select(Album.id, Album.title, Album.artist_id).order_by(Album.id)
        ).all()]


class TestArtistlessTracks:
    def test_artistless_track_does_not_join_another_artists_album(self, library_database):
        repo = library_database.tracks
        x = repo.add(_info(1, artists=['Someone']))
        y = repo.add(_info(2))

        assert y.album is not None
        assert y.album.id != x.album.id
        assert y.album.artist_id is None
        assert x.album.artist_id is not None

    def test_artistless_track_with_a_new_album_gets_one(self, library_database):
        z = library_database.tracks.add(_info(3, album='Orphan Album'))

        assert z.album is not None
        assert (z.album.title, z.album.artist_id) == ('Orphan Album', None)

    def test_artistless_tracks_of_one_album_share_it(self, library_database):
        repo = library_database.tracks
        a = repo.add(_info(4))
        b = repo.add(_info(5))

        assert a.album.id == b.album.id
        assert len(_albums(library_database)) == 1

    def test_rescan_assigns_the_same_album_as_the_first_scan(self, library_database):
        repo = library_database.tracks
        repo.add(_info(6, artists=['Someone']))  # another artist's same-title album exists
        first = repo.add(_info(7))

        rescanned = repo.update_by_filepath(first.filepath, _info(7))

        assert rescanned.album.id == first.album.id
        assert len(_albums(library_database)) == 2  # not a third, ownerless duplicate

    def test_retagging_an_artistless_track_moves_it_to_the_new_artists_album(self, library_database):
        repo = library_database.tracks
        track = repo.add(_info(8))
        ownerless_id = track.album.id

        updated = repo.update_by_filepath(track.filepath, _info(8, artists=['Someone']))

        assert updated.album.id != ownerless_id
        assert updated.album.artist_id is not None


def test_same_title_different_artists_stay_separate(library_database):
    repo = library_database.tracks
    a = repo.add(_info(10, artists=['A']))
    b = repo.add(_info(11, artists=['B']))

    assert a.album.id != b.album.id


def test_concurrent_adds_of_one_new_album_produce_one_row(library_database):
    """Both the owned and the ownerless album collapse a race to a single row."""
    start = threading.Barrier(8)
    results: list = []

    def worker(n: int) -> None:
        start.wait(timeout=10)
        owned = n % 2 == 0
        results.append(library_database.tracks.add(
            _info(n, album='Race', artists=['Racer'] if owned else [])
        ))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(20, 28)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sum(r is not None for r in results) == 8
    albums = _albums(library_database)
    assert sorted(a[1:] for a in albums if a[2] is None) == [('Race', None)]
    assert len([a for a in albums if a[2] is not None]) == 1
    with library_database.SessionLocal() as s:
        assert s.execute(select(func.count()).select_from(Track)).scalar_one() == 8


class TestMigrationMergesExistingDuplicates:
    def _database_at_v29_with_duplicates(self, db_path: Path) -> None:
        with MigrationManager(str(db_path)) as manager:
            assert manager.initialize_fresh_database()
            with manager.engine.begin() as conn:
                conn.execute(text("DROP INDEX uq_albums_title_artist"))
                conn.execute(text("DROP INDEX uq_albums_title_ownerless"))
                conn.execute(text("UPDATE schema_version SET version = 29"))
                conn.execute(text("INSERT INTO artists (id, name, normalized_name, total_plays) VALUES (1, 'A', 'a', 0), (2, 'B', 'b', 0)"))
                # ids 1,2: duplicate owned by A; 3,4,5: duplicate ownerless; 6: B's same-title album
                conn.execute(text(
                    "INSERT INTO albums (id, title, artist_id) VALUES "
                    "(1, 'Hits', 1), (2, 'Hits', 1), (3, 'Hits', NULL), (4, 'Hits', NULL), "
                    "(5, 'Hits', NULL), (6, 'Hits', 2), (7, 'hits', 1)"
                ))
                for track_id, album_id in enumerate((1, 2, 3, 4, 5, 6, 7), start=1):
                    conn.execute(text(
                        "INSERT INTO tracks (id, title, filepath, filepath_key, album_id, skip_count, favorite) "
                        f"VALUES ({track_id}, 't{track_id}', '/x/{track_id}', '/x/{track_id}', {album_id}, 0, 0)"
                    ))

    def test_duplicates_merge_into_the_lowest_id_and_tracks_follow(self, tmp_path):
        db_path = tmp_path / "dup.db"
        self._database_at_v29_with_duplicates(db_path)

        with MigrationManager(str(db_path)) as manager:
            assert manager.migrate_to_latest()
            assert manager.get_current_version() == __db_schema_version__

        with closing(sqlite3.connect(db_path)) as conn:
            assert conn.execute("SELECT id FROM albums ORDER BY id").fetchall() == [(1,), (3,), (6,), (7,)]
            assert conn.execute("SELECT id, album_id FROM tracks ORDER BY id").fetchall() == [
                (1, 1), (2, 1), (3, 3), (4, 3), (5, 3), (6, 6), (7, 7),
            ]
            names = {row[1] for row in conn.execute("PRAGMA index_list(albums)") if row[2]}
        assert names == {'uq_albums_title_artist', 'uq_albums_title_ownerless'}

    def test_the_indexes_reject_a_second_row(self, library_database):
        with library_database.SessionLocal() as s:
            s.execute(text("INSERT INTO albums (title) VALUES ('Solo')"))
            s.commit()
            try:
                s.execute(text("INSERT INTO albums (title) VALUES ('Solo')"))
            except Exception as exc:
                assert 'UNIQUE' in str(exc)
            else:
                raise AssertionError("duplicate ownerless album was accepted")
