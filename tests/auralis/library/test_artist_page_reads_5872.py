"""The artist page reads hydrate no Track row (#5872).

``GET /api/artists/{id}`` and ``/tracks`` used ``get_by_id``, which eager-loads
every Track (all columns, including the unbounded ``lyrics`` Text) and each
album's tracks again, so a large compilation artist cost hundreds of MB per
page open. ``get_page`` and ``get_track_rows`` read SQL aggregates and eight
scalar columns instead.
"""

from contextlib import contextmanager

import pytest
from sqlalchemy import event

from auralis.library.models import Album, Artist, Track


@pytest.fixture
def artist_id(session_factory):
    session = session_factory()
    try:
        artist = Artist(name="Various")
        session.add(artist)
        session.flush()
        older = Album(title="beta", year=2001, artist_id=artist.id)
        newer = Album(title="Alpha", year=2010, artist_id=artist.id)
        session.add_all([older, newer])
        session.flush()
        rows = [
            ("Loose", None, None, None),
            ("B2", older, 2, 1),
            ("B1", older, 1, 1),
            ("A-disc2", newer, 1, 2),
            ("A1", newer, 1, 1),
        ]
        for i, (title, album, number, disc) in enumerate(rows):
            track = Track(title=title, filepath=f"/{i}.flac", duration=100.0 + i,
                          album=album, track_number=number, disc_number=disc,
                          lyrics="la " * 1000)
            track.artists = [artist]
            session.add(track)
        session.commit()
        return artist.id
    finally:
        session.close()


@contextmanager
def _statements(session_factory):
    engine = session_factory().get_bind()
    sink: list[str] = []

    def record(conn, cursor, statement, *args):
        sink.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield sink
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_get_page_counts_in_sql_and_never_selects_a_track_row(session_factory, artist_repository, artist_id):
    with _statements(session_factory) as sql:
        artist = artist_repository.get_page(artist_id)

    assert artist.track_count_expr == 5
    by_title = {album.title: album for album in artist.albums}
    assert by_title["beta"].track_count_expr == 2
    assert by_title["beta"].total_duration_expr == pytest.approx(101.0 + 102.0)
    assert by_title["Alpha"].artist.name == "Various"  # serialize_album reads it
    assert not any("tracks.lyrics" in statement for statement in sql)


def test_get_track_rows_is_column_narrow_and_sorted_in_sql(session_factory, artist_repository, artist_id):
    with _statements(session_factory) as sql:
        name, rows = artist_repository.get_track_rows(artist_id)

    assert name == "Various"
    # Album-less first, then album title case-insensitively, disc, track number.
    assert [row["title"] for row in rows] == ["Loose", "A1", "A-disc2", "B1", "B2"]
    assert set(rows[0]) == {
        "id", "title", "album", "album_id", "duration", "track_number", "disc_number", "format",
    }
    assert rows[0]["album"] is None and rows[1]["album"] == "Alpha"
    assert not any("tracks.lyrics" in statement for statement in sql)


def test_missing_artist(artist_repository):
    assert artist_repository.get_page(999_999) is None
    assert artist_repository.get_track_rows(999_999) is None


def test_serializing_the_page_albums_logs_no_detached_instance_warning(artist_repository, artist_id, caplog):
    """#5961: get_by_id left Album.artist unloaded, so every album on the page
    logged a detached-instance WARNING and reported its artist as None."""
    artist = artist_repository.get_page(artist_id)

    with caplog.at_level("WARNING"):
        serialized = [album.to_dict() for album in artist.albums]

    assert {album["artist"] for album in serialized} == {"Various"}
    assert "could not be loaded" not in caplog.text
