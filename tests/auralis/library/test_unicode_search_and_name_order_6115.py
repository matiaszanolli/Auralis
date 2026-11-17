"""Search folds case in every script; genre and playlist lists sort A-Z (#6115).

SQLite's ``lower()``/``LIKE`` fold ASCII only, so ``ilike()`` never matched a
stored "Sigur Rós" for "SIGUR RÓS". Genre and playlist lists ordered with the
BINARY collation, putting every lowercase initial after "Z".

The ``session_factory`` fixture builds its own engine, not LibraryDatabase's, so
these tests also show the casefold() function reaches every engine.
"""

import pytest

from auralis.library.models import Album, Artist, Genre, Track
from auralis.library.repositories.album_repository import AlbumRepository
from auralis.library.repositories.artist_repository import ArtistRepository
from auralis.library.repositories.genre_repository import GenreRepository
from auralis.library.repositories.playlist_repository import PlaylistRepository
from auralis.library.repositories.track_repository import TrackRepository


@pytest.fixture
def seeded(session_factory):
    session = session_factory()
    try:
        artist = Artist(name="Sigur Rós", normalized_name="sigur ros")
        session.add(artist)
        session.flush()
        album = Album(title="Ágætis byrjun", artist_id=artist.id)
        session.add(album)
        session.flush()
        track = Track(title="Svefn-g-englar", filepath="/svefn.flac", album_id=album.id)
        track.artists.append(artist)
        session.add(track)
        session.add(Track(title="éclair", filepath="/eclair.flac"))
        session.add(Track(title="Straße", filepath="/strasse.flac"))
        session.add_all(Genre(name=name) for name in ("blues", "Ambient", "électronique", "Zydeco", "Jazz"))
        session.commit()
    finally:
        session.close()
    return session_factory


@pytest.mark.parametrize("query", ["SIGUR RÓS", "sigur rós", "Sigur Rós"])
def test_artist_search_matches_every_case_of_a_non_ascii_name(seeded, query):
    artists, total = ArtistRepository(seeded).search(query)
    assert total == 1
    assert [a.name for a in artists] == ["Sigur Rós"]


@pytest.mark.parametrize("query", ["ÉCLAIR", "Éclair", "éclair"])
def test_track_search_matches_every_case_of_a_non_ascii_title(seeded, query):
    tracks, total = TrackRepository(seeded).search(query)
    assert total == 1
    assert [t.title for t in tracks] == ["éclair"]


def test_track_search_reaches_the_artist_and_album_columns(seeded):
    repo = TrackRepository(seeded)
    by_artist, _ = repo.search("SIGUR RÓS")
    by_album, _ = repo.search("ÁGÆTIS")
    assert [t.title for t in by_artist] == [t.title for t in by_album] == ["Svefn-g-englar"]


def test_full_casefolding_matches_sharp_s(seeded):
    tracks, _ = TrackRepository(seeded).search("STRASSE")
    assert [t.title for t in tracks] == ["Straße"]


def test_album_search_matches_title_and_artist_across_case(seeded):
    repo = AlbumRepository(seeded)
    by_title, _ = repo.search("ÁGÆTIS BYRJUN")
    by_artist, _ = repo.search("SIGUR RÓS")
    assert [a.title for a in by_title] == [a.title for a in by_artist] == ["Ágætis byrjun"]


def test_genre_search_matches_across_case(seeded):
    genres, total = GenreRepository(seeded).search("ÉLECTRO")
    assert total == 1
    assert [g.name for g in genres] == ["électronique"]


def test_playlist_search_matches_name_and_description_across_case(session_factory):
    repo = PlaylistRepository(session_factory)
    repo.create("Ólafur Arnalds", "piano")
    repo.create("Driving", "música para el coche")
    by_name, _ = repo.search("ÓLAFUR")
    by_description, _ = repo.search("MÚSICA")
    assert [p.name for p in by_name] == ["Ólafur Arnalds"]
    assert [p.name for p in by_description] == ["Driving"]


def test_search_still_treats_like_metacharacters_literally(seeded):
    tracks, total = TrackRepository(seeded).search("%")
    assert (tracks, total) == ([], 0)


def test_genre_list_sorts_case_insensitively(seeded):
    genres, _ = GenreRepository(seeded).get_all()
    # NOCASE folds ASCII; the accented initial still sorts after the ASCII letters.
    assert [g.name for g in genres] == ["Ambient", "blues", "Jazz", "Zydeco", "électronique"]


def test_genre_search_sorts_case_insensitively(seeded):
    genres, _ = GenreRepository(seeded).search("E")
    assert [g.name for g in genres] == ["Ambient", "blues", "Zydeco", "électronique"]


def test_playlist_list_and_search_sort_case_insensitively(session_factory):
    repo = PlaylistRepository(session_factory)
    for name in ("road trip", "Morning", "chill", "Zen"):
        repo.create(name, "mix")
    listed, _ = repo.get_all()
    searched, _ = repo.search("MIX")
    expected = ["chill", "Morning", "road trip", "Zen"]
    assert [p.name for p in listed] == expected
    assert [p.name for p in searched] == expected
