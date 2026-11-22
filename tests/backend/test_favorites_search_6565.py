"""GET /api/library/tracks/favorites honours ?search= (#6565).

#5866 gave /api/library/tracks server-side search; the favourites route took only
limit/offset, so FastAPI dropped the frontend's ?search= and returned unfiltered
favourites. Searching for a favourite outside the loaded pages showed "no results".
"""

import pytest


@pytest.fixture
def favourites(client, tmp_path):
    """Four favourites and one non-favourite that also matches the query."""
    from main import globals_dict

    tracks = globals_dict["library_database"].tracks
    made = []
    for i, (title, artist, favourite) in enumerate([
        ("Blue Train", "Coltrane", True),
        ("Giant Steps", "Coltrane", True),
        ("So What", "Davis", True),
        ("Freddie Freeloader", "Davis", True),
        ("Blue in Green", "Davis", False),
    ]):
        path = tmp_path / f"t{i}.wav"
        path.write_bytes(b"")
        track = tracks.add({
            "title": title, "filepath": str(path), "artists": [artist], "album": "Jazz",
            "format": "WAV", "sample_rate": 44100, "channels": 2, "duration": 60.0,
        })
        assert track is not None
        if favourite:
            assert tracks.set_favorite(track.id, True)
        made.append(track)
    yield made
    for track in made:
        tracks.delete(track.id)


def _titles(body):
    return sorted(t["title"] for t in body["tracks"])


def test_search_narrows_favourites_and_their_total(client, favourites):
    body = client.get("/api/library/tracks/favorites", params={"search": "blue"}).json()
    # "Blue in Green" matches the text but is not a favourite.
    assert _titles(body) == ["Blue Train"]
    assert body["total"] == 1


def test_search_matches_the_artist_like_the_main_track_list(client, favourites):
    body = client.get("/api/library/tracks/favorites", params={"search": "coltrane"}).json()
    assert _titles(body) == ["Blue Train", "Giant Steps"]
    assert body["total"] == 2


def test_search_reaches_favourites_beyond_the_first_page(client, favourites):
    body = client.get("/api/library/tracks/favorites", params={"search": "freddie", "limit": 1}).json()
    assert _titles(body) == ["Freddie Freeloader"]
    assert body["total"] == 1


def test_no_search_still_lists_every_favourite(client, favourites):
    body = client.get("/api/library/tracks/favorites").json()
    assert _titles(body) == ["Blue Train", "Freddie Freeloader", "Giant Steps", "So What"]
    assert body["total"] == 4
