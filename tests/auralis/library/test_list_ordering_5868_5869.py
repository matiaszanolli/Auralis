"""Paginated list order: direction, NULL placement and case-insensitivity (#5868, #5869).

The album/artist/track list reads could only ascend (so "newest first" was
impossible server-side and the grid re-sorted whatever pages it had), put NULL
years first, and ordered names with SQLite's BINARY collation — every
lowercase initial after ``Z``.
"""

import pytest
from sqlalchemy import select, text

from auralis.library.models import Album, Artist, Track
from auralis.library.repositories.base import sort_terms


@pytest.fixture
def seeded(session_factory):
    session = session_factory()
    try:
        artists = [Artist(name=name) for name in ("Beta Band", "alt-J", "Abba", "deadmau5")]
        session.add_all(artists)
        session.flush()
        owner = artists[0].id
        session.add_all([
            Album(title="Zed", year=1990, artist_id=owner),
            Album(title="apple", year=None, artist_id=owner),
            Album(title="Mango", year=2020, artist_id=owner),
            Album(title="banana", year=2005, artist_id=owner),
            Album(title="Kiwi", year=2020, artist_id=owner),
        ])
        session.add_all([
            Track(title=title, filepath=f"/{title}.flac", favorite=True)
            for title in ("Zebra", "aardvark", "Moose", "bison")
        ])
        session.commit()
    finally:
        session.close()


def _titles(albums):
    return [album.title for album in albums]


@pytest.mark.usefixtures("seeded")
class TestAlbumOrder:
    def test_titles_sort_case_insensitively(self, album_repository):
        albums, _ = album_repository.get_all(order_by='title')
        assert _titles(albums) == ["apple", "banana", "Kiwi", "Mango", "Zed"]

    def test_year_desc_is_newest_first_with_undated_last_and_an_id_tiebreak(self, album_repository):
        albums, _ = album_repository.get_all(order_by='year', order='desc')
        # Mango and Kiwi share 2020: the id tie-breaker follows the direction.
        assert _titles(albums) == ["Kiwi", "Mango", "banana", "Zed", "apple"]

    def test_year_asc_still_puts_undated_albums_last(self, album_repository):
        albums, _ = album_repository.get_all(order_by='year')
        assert _titles(albums)[-1] == "apple"
        assert _titles(albums)[0] == "Zed"

    def test_pages_tile_the_desc_order(self, album_repository):
        whole, _ = album_repository.get_all(order_by='year', order='desc')
        pages = [album_repository.get_all(limit=2, offset=o, order_by='year', order='desc')[0]
                 for o in (0, 2, 4)]
        assert _titles([a for page in pages for a in page]) == _titles(whole)

    def test_search_uses_the_same_order(self, album_repository):
        # Every album matches: search also hits the artist name ("Beta Band").
        albums, _ = album_repository.search("a", order_by='title', order='desc')
        assert _titles(albums) == ["Zed", "Mango", "Kiwi", "banana", "apple"]


@pytest.mark.usefixtures("seeded")
class TestArtistOrder:
    def test_lowercase_initials_sort_with_their_letter(self, artist_repository):
        artists, _ = artist_repository.get_all(order_by='name')
        assert [a.name for a in artists] == ["Abba", "alt-J", "Beta Band", "deadmau5"]

    def test_name_desc(self, artist_repository):
        artists, _ = artist_repository.search("a", order_by='name', order='desc')
        assert [a.name for a in artists] == ["deadmau5", "Beta Band", "alt-J", "Abba"]

    def test_counts_default_most_first_and_asc_reverses_them(self, artist_repository):
        most_first, _ = artist_repository.get_all(order_by='album_count')
        least_first, _ = artist_repository.get_all(order_by='album_count', order='asc')
        assert most_first[0].name == "Beta Band"
        assert least_first[-1].name == "Beta Band"


@pytest.mark.usefixtures("seeded")
class TestTrackOrder:
    def test_titles_sort_case_insensitively(self, track_repository):
        tracks, _ = track_repository.get_all(order_by='title')
        assert [t.title for t in tracks] == ["aardvark", "bison", "Moose", "Zebra"]

    def test_title_desc(self, track_repository):
        tracks, _ = track_repository.get_all(order_by='title', order='desc')
        assert [t.title for t in tracks] == ["Zebra", "Moose", "bison", "aardvark"]

    def test_favorites_sort_case_insensitively(self, track_repository):
        tracks, _ = track_repository.get_favorites()
        assert [t.title for t in tracks] == ["aardvark", "bison", "Moose", "Zebra"]


@pytest.mark.parametrize(
    ("model", "column", "index"),
    [
        (Album, Album.title, "idx_albums_title"),
        (Track, Track.title, "idx_tracks_title"),
        (Artist, Artist.name, "idx_artists_name"),
    ],
)
@pytest.mark.parametrize("descending", [False, True])
def test_the_name_sort_is_backed_by_the_nocase_index(session_factory, model, column, index, descending):
    """The NOCASE ORDER BY walks the matching index instead of sorting in a temp B-tree."""
    statement = select(model.id).order_by(*sort_terms(column, model.id, descending=descending))
    compiled = statement.compile(compile_kwargs={"literal_binds": True})
    session = session_factory()
    try:
        plan = " ".join(row[-1] for row in session.execute(text(f"EXPLAIN QUERY PLAN {compiled}")))
    finally:
        session.close()
    assert index in plan
    assert "TEMP B-TREE" not in plan
