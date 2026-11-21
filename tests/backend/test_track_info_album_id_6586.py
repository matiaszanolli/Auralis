"""TrackInfo carries the album id, also for a track whose album has no artwork yet (#6586).

The player bar read the album id out of `artwork_url`. For a track loaded before its album had art
that URL is null, so an `artwork_updated` for the album could never reach the bar.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from player_state import create_track_info  # noqa: E402


class _Album:
    def __init__(self, album_id: int, artwork_path: str | None):
        self.id = album_id
        self.title = "Album"
        self.artwork_path = artwork_path


class _Track:
    def __init__(self, album: _Album | None, album_id: object = None):
        self.id = 1
        self.title = "Song"
        self.duration = 123.0
        self.filepath = "/srv/music/song.flac"
        self.album = album
        self.album_id = album_id
        self.artists = []
        self.format = "flac"


def test_a_track_whose_album_has_no_artwork_still_names_its_album():
    info = create_track_info(_Track(_Album(7, artwork_path=None), album_id=7))

    assert info.model_dump()["album_id"] == 7
    assert info.artwork_url is None


def test_the_album_id_comes_from_the_relationship_when_the_column_is_unset():
    info = create_track_info(_Track(_Album(9, artwork_path="/art/9.jpg")))

    assert info.album_id == 9
    assert info.artwork_url == "/api/albums/9/artwork"


def test_a_track_without_an_album_sends_null():
    assert create_track_info(_Track(None)).model_dump()["album_id"] is None


def test_a_non_integer_album_id_is_dropped_rather_than_failing_validation():
    info = create_track_info(_Track(None, album_id=Mock()))

    assert info.album_id is None
