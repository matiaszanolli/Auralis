"""Track `format` is carried to the client; `filepath` never is (#4586).

The audit reported that artist and playlist queue-population payloads omit
`filepath`, while the frontend `Track` contract declared it required. Tracing
it showed the premise was inverted:

  * `serialize_object()` prefers `obj.to_dict()` whenever the object has one,
    and `Track.to_dict()` omits `filepath` — so switching the playlist route to
    `serialize_track` (the proposed fix) would have changed nothing;
  * #3205 deliberately made the path server-only
    (`player_state.TrackInfo.filepath = Field(exclude=True)`);
  * queue entries are re-hydrated from `TrackInfo` dicts by every
    `queue_changed` broadcast, so any REST-supplied `filepath` is overwritten
    within a second anyway.

What the consumers (`queue_recommender`, `queue_statistics`) actually wanted
was the *format*, which they were deriving by parsing the absent path. So the
contract is: `format` travels, `filepath` does not.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))


class _FakeTrack:
    """Minimal stand-in for the ORM Track attributes these paths read."""

    def __init__(self, fmt="flac"):
        self.id = 1
        self.title = "Song"
        self.duration = 123.0
        self.filepath = "/srv/music/library/Song.flac"
        self.album_id = 7
        self.album = None
        self.artists = []
        self.format = fmt


class TestTrackInfoCarriesFormat:

    def test_track_info_exposes_format(self):
        from player_state import create_track_info

        info = create_track_info(_FakeTrack("flac"))
        assert info is not None
        assert info.format == "flac"

    def test_track_info_still_hides_filepath_from_serialization(self):
        """#3205 must survive: the path stays server-side."""
        from player_state import create_track_info

        info = create_track_info(_FakeTrack())
        dumped = info.model_dump()

        assert "filepath" not in dumped, (
            "the server-side path leaked back into API/WS payloads — #3205 regressed"
        )
        # Still available in-process for the player to load the file.
        assert info.filepath == "/srv/music/library/Song.flac"

    def test_format_is_optional_for_tracks_that_lack_it(self):
        from player_state import create_track_info

        class _NoFormat(_FakeTrack):
            def __init__(self):
                super().__init__()
                del self.format

        info = create_track_info(_NoFormat())
        assert info is not None and info.format is None


class TestArtistTrackCarriesFormat:

    def test_track_in_artist_has_a_format_field(self):
        from routers.artists import TrackInArtist

        track = TrackInArtist(
            id=1, title="Song", album="Album", album_id=2, duration=10.0, format="mp3"
        )
        assert track.format == "mp3"
        assert "format" in track.model_dump()

    def test_format_defaults_to_none(self):
        from routers.artists import TrackInArtist

        track = TrackInArtist(id=1, title="S", album="A", album_id=2, duration=1.0)
        assert track.format is None


class TestSerializerFilepathConsistency:

    def test_default_track_fields_omits_filepath(self):
        """Both serializer paths must agree that no path is emitted (#4586).

        `serialize_object` prefers `to_dict()` (which omits it) and falls back
        to `getattr` over these defaults; listing `filepath` here made the two
        paths disagree for Mocks and detached instances.
        """
        from routers.serializers import DEFAULT_TRACK_FIELDS

        assert "filepath" not in DEFAULT_TRACK_FIELDS

    def test_default_track_fields_includes_format(self):
        from routers.serializers import DEFAULT_TRACK_FIELDS

        assert "format" in DEFAULT_TRACK_FIELDS

    def test_orm_to_dict_and_serializer_agree_about_filepath(self):
        from auralis.library.models.core import Track
        from routers.serializers import serialize_track

        track = Track(id=1, title="X", filepath="/music/a.flac", duration=10.0)
        assert "filepath" not in track.to_dict()
        assert "filepath" not in serialize_track(track)

    def test_serialized_track_still_carries_format(self):
        """The field the queue utilities actually need."""
        from auralis.library.models.core import Track
        from routers.serializers import serialize_track

        track = Track(id=1, title="X", filepath="/music/a.flac", duration=10.0, format="flac")
        assert serialize_track(track)["format"] == "flac"
