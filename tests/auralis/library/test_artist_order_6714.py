"""A track's artists keep their tag order (#6714).

track_artist had no position column, so SQLite returned a track's artists in
query-plan order and readers that take artists[0] as the primary artist could
show a featured one. The order is stored now, and v32 -> v33 backfills it.
"""

import sqlite3
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from auralis.__version__ import __db_schema_version__
from auralis.library.migration_manager import MigrationManager
from auralis.library.models import Artist, Track


def _track_info(path: str, artists: list[str]) -> dict:
    return {
        "filepath": path, "title": Path(path).stem, "artists": artists,
        "duration": 1.0, "sample_rate": 44100, "channels": 2, "format": "FLAC", "filesize": 10,
    }


def _names(track) -> list[str]:
    return [artist.name for artist in track.artists]


def test_artists_reload_in_tag_order_not_id_order(library_database):
    # "Alpha" gets the lower id, so id order and tag order disagree.
    library_database.tracks.add(_track_info("/music/first.flac", ["Alpha"]))
    track = library_database.tracks.add(_track_info("/music/duet.flac", ["Beta", "Alpha"]))

    assert track is not None
    assert _names(library_database.tracks.get_by_id(track.id)) == ["Beta", "Alpha"]


def test_an_update_that_only_reorders_the_artists_sticks(library_database):
    track = library_database.tracks.add(_track_info("/music/duet.flac", ["Beta", "Alpha"]))
    assert track is not None

    # Both directions: the links themselves never change, so whatever order the
    # rows read back in unaided, one of the two would come out wrong.
    for order in (["Alpha", "Beta"], ["Beta", "Alpha"]):
        library_database.tracks.update(track.id, {"artists": order})
        assert _names(library_database.tracks.get_by_id(track.id)) == order


def test_two_spellings_of_one_artist_link_it_once_at_its_first_place(library_database):
    track = library_database.tracks.add(_track_info("/music/trio.flac", ["Gamma", "Delta", "gamma"]))

    assert track is not None
    assert [name.lower() for name in _names(library_database.tracks.get_by_id(track.id))] == ["gamma", "delta"]


def _v32_library(db_path: Path, *, with_position: bool) -> None:
    """Track 1 linked to artists 2 then 1 (rowid order = tag order), track 2 to artist 1 only."""
    with MigrationManager(str(db_path)) as manager:
        assert manager.initialize_fresh_database()
        with manager.engine.begin() as conn:
            conn.execute(text("UPDATE schema_version SET version = 32"))
            if not with_position:
                conn.execute(text("ALTER TABLE track_artist DROP COLUMN position"))
        with sessionmaker(bind=manager.engine)() as session:
            session.add_all([Track(id=n, title=f"T{n}", filepath=f"/m/{n}.flac", filepath_key=f"/m/{n}.flac")
                             for n in (1, 2)])
            session.add_all([Artist(id=1, name="One", normalized_name="one"),
                             Artist(id=2, name="Two", normalized_name="two")])
            session.commit()
        with manager.engine.begin() as conn:
            if with_position:
                conn.execute(text(
                    "INSERT INTO track_artist (track_id, artist_id, position) VALUES (1, 2, 1), (1, 1, 0)"
                ))
            else:
                conn.execute(text("INSERT INTO track_artist (track_id, artist_id) VALUES (1, 2), (1, 1), (2, 1)"))


def _links(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT track_id, artist_id, position FROM track_artist ORDER BY rowid").fetchall()
    finally:
        conn.close()


def _migrate(db_path: Path) -> None:
    with MigrationManager(str(db_path)) as manager:
        assert manager.migrate_to_latest()
        assert manager.get_current_version() == __db_schema_version__


def test_upgrading_backfills_position_from_insertion_order(tmp_path):
    db_path = tmp_path / "library.db"
    _v32_library(db_path, with_position=False)

    _migrate(db_path)

    assert _links(db_path) == [(1, 2, 0), (1, 1, 1), (2, 1, 0)]


def test_a_replay_never_overwrites_stored_positions(tmp_path):
    db_path = tmp_path / "library.db"
    _v32_library(db_path, with_position=True)

    _migrate(db_path)

    assert _links(db_path) == [(1, 2, 1), (1, 1, 0)]
