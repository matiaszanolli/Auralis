"""One representation for an absent album / artist across library endpoints (#5905).

A missing album or artist used to be `null` on track lists, `"Unknown Album"` /
`album_id: 0` on `/api/artists/{id}/tracks`, and `"Unknown Artist"` on albums,
and `total_tracks` meant the tag-declared count on `AlbumResponse` but the
actual row count on `AlbumTracksResponse` / `ArtistDetailResponse`. Absence is
now `null` (`[]` for a track's artist list) everywhere and the frontend supplies
the label at its API boundary. The tag-declared count is `declared_track_count`.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.models import Album  # noqa: E402
from routers.albums import get_album_tracks  # noqa: E402
from routers.artists import get_artist_tracks  # noqa: E402
from routers.artists_models import TrackInArtist  # noqa: E402
from routers.serializers_library import serialize_album  # noqa: E402
from schemas import AlbumResponse  # noqa: E402


def _artist_with_tracks(*tracks):
    return SimpleNamespace(id=1, name="The Artist", tracks=list(tracks))


def _track(id, title, album=None):
    return SimpleNamespace(
        id=id, title=title, album=album, duration=100.0,
        track_number=1, disc_number=1, format="FLAC",
    )


def test_album_less_track_in_artist_tracks_has_null_album_and_album_id():
    artist = _artist_with_tracks(_track(1, "Loose"))
    repos = MagicMock()
    repos.artists.get_by_id.return_value = artist

    response = asyncio.run(get_artist_tracks(artist_id=1, repos=repos))

    [track] = response.tracks
    assert track.album is None
    assert track.album_id is None


def test_artist_tracks_with_and_without_albums_sort_without_error():
    album = SimpleNamespace(id=7, title="Zed")
    artist = _artist_with_tracks(_track(1, "On Album", album), _track(2, "Loose"))
    repos = MagicMock()
    repos.artists.get_by_id.return_value = artist

    response = asyncio.run(get_artist_tracks(artist_id=1, repos=repos))

    assert [t.title for t in response.tracks] == ["Loose", "On Album"]
    assert response.tracks[1].album_id == 7
    assert response.total_tracks == 2


def test_track_in_artist_accepts_null_album_fields():
    track = TrackInArtist(id=1, title="t", duration=1.0)

    assert track.album is None and track.album_id is None


def test_album_without_an_artist_has_null_artist_on_list_and_tracks_endpoints():
    album = SimpleNamespace(
        id=3, title="Orphan", artist=None, year=None, artwork_path=None, tracks=[],
    )
    repos = MagicMock()
    repos.albums.get_by_id.return_value = album

    from_tracks_endpoint = asyncio.run(get_album_tracks(album_id=3, repos=repos))

    assert from_tracks_endpoint["artist"] is None
    assert Album(title="Orphan").to_dict()["artist"] is None


def test_album_tag_count_is_declared_track_count_and_total_tracks_keeps_one_meaning():
    album = Album(title="Declared", total_tracks=12)
    payload = album.to_dict()

    assert payload["declared_track_count"] == 12
    assert "total_tracks" not in payload
    assert payload["track_count"] == 0  # the real row count, a different quantity
    assert "declared_track_count" in AlbumResponse.model_fields
    assert "total_tracks" not in AlbumResponse.model_fields


def test_serialized_album_carries_the_renamed_field():
    assert serialize_album(Album(title="X", total_tracks=5))["declared_track_count"] == 5
