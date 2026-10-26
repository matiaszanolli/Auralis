"""
Tests for shared serialization utilities.

Key invariants verified:
- Track serialization NEVER exposes 'filepath' (security/privacy)
- Graceful fallback when to_dict() is unavailable or raises
- Album total_duration and track_count derived from relations
- Artist/playlist counts derived from related collections
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

_backend_dir = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
sys.path.insert(0, str(_backend_dir))

if 'routers' not in sys.modules:
    _stub = types.ModuleType('routers')
    _stub.__path__ = [str(_backend_dir / 'routers')]
    _stub.__package__ = 'routers'
    sys.modules['routers'] = _stub

from routers.serializers import serialize_object, serialize_objects
from routers.serializers_library import (
    serialize_album,
    serialize_albums,
    serialize_artist,
    serialize_playlist,
    serialize_playlists,
    serialize_tracks,
)


# ---------------------------------------------------------------------------
# Helper: lightweight object with a fixed to_dict()
# ---------------------------------------------------------------------------

class _FakeModel:
    """Lightweight non-Mock object whose to_dict() returns a fixed dict."""
    def __init__(self, dict_result: dict, **attrs):
        self._dict_result = dict_result
        for k, v in attrs.items():
            setattr(self, k, v)

    def to_dict(self) -> dict:
        return self._dict_result


_UNSET = object()  # sentinel: "don't set this attribute at all" vs. "set it to None"


# ---------------------------------------------------------------------------
# serialize_object — to_dict() is the only source of the response shape (#5803)
# ---------------------------------------------------------------------------

class TestSerializeObject:
    def test_uses_to_dict(self):
        obj = _FakeModel({"id": 42, "title": "Song"})
        assert serialize_object(obj) == {"id": 42, "title": "Song"}

    def test_returns_empty_dict_for_none(self):
        assert serialize_object(None) == {}

    def test_does_not_merge_attributes_into_to_dict(self):
        """Attributes that to_dict() does not emit stay out of the response."""
        obj = _FakeModel({"id": 1}, title="Not in to_dict", genre="Doom")
        assert serialize_object(obj) == {"id": 1}

    def test_a_raising_to_dict_propagates_and_is_logged(self, caplog):
        class _BrokenModel:
            def to_dict(self):
                raise RuntimeError("detached session")

        with caplog.at_level("ERROR", logger="routers.serializers"):
            with pytest.raises(RuntimeError, match="detached session"):
                serialize_object(_BrokenModel())
        assert "_BrokenModel" in caplog.text

    def test_an_object_without_to_dict_is_rejected(self):
        with pytest.raises(AttributeError):
            serialize_object(object())

    def test_a_non_dict_to_dict_result_is_rejected(self):
        """An unconfigured Mock's to_dict() returns another Mock; it must not
        be silently projected into a response."""
        with pytest.raises(TypeError, match="not dict"):
            serialize_object(MagicMock())

    def test_serialize_objects_maps_over_the_list(self):
        objs = [_FakeModel({"id": 1}), _FakeModel({"id": 2})]
        assert serialize_objects(objs) == [{"id": 1}, {"id": 2}]


# ---------------------------------------------------------------------------
# serialize_tracks — sensitive field exclusion
# ---------------------------------------------------------------------------

class TestSerializeTrack:
    def _make_track(self, **overrides):
        """Build a real (non-Mock) track whose to_dict() returns safe fields only."""
        defaults = {
            'id': 1,
            'title': 'Test Track',
            'duration': 180.0,
            'format': 'FLAC',
            'artists': ['Artist A'],
            'album': 'Album X',
        }
        defaults.update(overrides)
        return _FakeModel(defaults)

    def test_filepath_absent_from_serialized_track(self):
        track = self._make_track()
        result = serialize_tracks([track])[0]
        assert 'filepath' not in result

    def test_safe_fields_present(self):
        track = self._make_track()
        result = serialize_tracks([track])[0]
        assert result['id'] == 1
        assert result['title'] == 'Test Track'

    def test_real_track_to_dict_has_no_filepath_or_fallback_twins(self):
        """The real key set: no server-side path (#3205) and one spelling per
        field (#5823) -- `artists`/`genres`/`created_at`/
        `updated_at`, never the singular or aliased twins."""
        from auralis.library.models import Track

        result = serialize_tracks([Track(title="T")])[0]
        assert 'filepath' not in result
        for twin in ('artist', 'genre', 'loudness', 'date_added', 'date_modified'):
            assert twin not in result
        for key in ('artists', 'genres', 'created_at', 'updated_at'):
            assert key in result

    def test_serialize_tracks_list(self):
        tracks = [self._make_track(id=i) for i in range(3)]
        results = serialize_tracks(tracks)
        assert len(results) == 3
        for r in results:
            assert 'filepath' not in r

    def test_serialize_tracks_empty_list(self):
        assert serialize_tracks([]) == []

    def test_serialize_objects_delegates_to_serialize_object(self):
        objs = [self._make_track(id=1), self._make_track(id=2)]
        assert [r['id'] for r in serialize_objects(objs)] == [1, 2]


# ---------------------------------------------------------------------------
# serialize_album — duration and count derivation
# ---------------------------------------------------------------------------

class TestSerializeAlbum:
    """#4777: total_duration/track_count are computed by Album.to_dict()
    (preferring the repository's SQL aggregates, falling back to walking
    `tracks` only when the query didn't supply them) — NOT re-derived here.
    serialize_album must trust to_dict()'s values as-is and must never touch
    `album.tracks` directly, since AlbumRepository.get_all()/.search()/
    .get_recent() no longer eager-load that collection (#4777), and a real
    detached ORM instance raises DetachedInstanceError (not caught by
    `hasattr()`) on an unloaded relationship access."""

    def _make_album(self, track_count: int = 0, total_duration: float = 0, tracks: object = _UNSET):
        dict_result = {
            'id': 10,
            'title': 'Album A',
            'artist': 'Artist B',
            'year': 2020,
            'artwork_path': None,
            'track_count': track_count,
            'total_duration': total_duration,
        }
        attrs = {} if tracks is _UNSET else {'tracks': tracks}
        return _FakeModel(dict_result, **attrs)

    def test_total_duration_passed_through_from_to_dict(self):
        album = self._make_album(total_duration=360.0)
        result = serialize_album(album)
        assert result['total_duration'] == 360.0

    def test_track_count_passed_through_from_to_dict(self):
        album = self._make_album(track_count=2)
        result = serialize_album(album)
        assert result['track_count'] == 2

    def test_zero_track_count_and_duration_passed_through_unchanged(self):
        """A genuinely-empty album (to_dict() reports 0/0) must stay 0/0 —
        not get silently re-derived from a tracks collection."""
        album = self._make_album(track_count=0, total_duration=0)
        result = serialize_album(album)
        assert result['track_count'] == 0
        assert result['total_duration'] == 0

    def test_does_not_access_tracks_attribute_at_all(self):
        """Regression guard: touching `album.tracks` on a real detached ORM
        instance whose tracks relationship wasn't eager-loaded raises
        DetachedInstanceError, which `hasattr()` does not catch. Simulate
        that with a `tracks` property that raises on access — serialize_album
        must never trigger it."""
        class _ExplodingTracks:
            @property
            def tracks(self):
                raise RuntimeError("tracks accessed — should never happen")

        album = _ExplodingTracks()
        album.to_dict = lambda: {  # type: ignore[method-assign]
            'id': 10, 'title': 'Album A', 'track_count': 5, 'total_duration': 300.0,
        }
        result = serialize_album(album)  # must not raise
        assert result['track_count'] == 5
        assert result['total_duration'] == 300.0

    def test_serialize_albums_list(self):
        albums = [self._make_album(track_count=1, total_duration=60.0) for _ in range(3)]
        results = serialize_albums(albums)
        assert len(results) == 3


class TestAlbumDetailSharesTheListingShape:
    """`GET /api/albums/{id}` emits the same snake_case shape as the listing (#4679).

    #4423 gave the detail endpoint a camelCase serializer of its own. Nothing
    ever consumed it — `useAlbumDetails.ts` reads the sibling {id}/tracks
    endpoint — while the frontend declared exactly one Album contract
    (`AlbumApiResponse`, snake_case) and one transformer (`transformAlbum`),
    which pointed at the detail endpoint would have produced an all-undefined
    Album. The variant is deleted; both endpoints now go through
    `serialize_album`.
    """

    def _make_album(self, extra=None, track_count: int = 0, total_duration: float = 0):
        # Mirrors Album.to_dict()'s real key set. It deliberately carries NO
        # 'genre': Album has no genre column, so a `'genre': 'Rock'` fixture
        # would be a key production can never emit — and that is how the old
        # camelCase serializer's phantom genre mapping went unnoticed (#4709,
        # same shape as #4830/#4833).
        dict_result = {
            'id': 10,
            'title': 'Album A',
            'artist': 'Artist B',
            'artist_id': 7,
            'year': 2020,
            'total_tracks': None,
            'total_discs': None,
            # Album.to_dict() converts artwork_path to an API URL and emits
            # `artwork_url`. The pre-#4679 fixture spelled this `artwork_path`
            # while claiming to mirror to_dict()'s key set; the camelCase
            # serializer read `snake.get('artwork_url')`, so the mismatch
            # resolved to None either way and went unnoticed.
            'artwork_url': None,
            'avg_dr_rating': None,
            'avg_lufs': None,
            'mastering_consistency': None,
            'track_count': track_count,
            'total_duration': total_duration,
            'created_at': None,
            'updated_at': None,
        }
        if extra:
            dict_result.update(extra)
        return _FakeModel(dict_result)

    def test_the_fixture_matches_the_real_to_dict_key_set(self):
        """Guards the mismatch above from silently returning."""
        from auralis.library.models import Album

        assert set(self._make_album().to_dict()) == set(Album().to_dict())

    def test_the_camelcase_serializer_is_gone(self):
        """The lone camelCase producer must not come back (#4679)."""
        import routers.serializers as serializers_module

        assert not hasattr(serializers_module, 'serialize_album_detail')

    def test_detail_route_uses_the_listing_serializer_and_model(self):
        """get_album must register with AlbumResponse and return serialize_album().

        #4670 hoisted albums.py's handlers to module level and switched
        registration from `@router.get(...)` decorators to
        `router.add_api_route(...)` calls in a short assembler -- there is no
        single decorated block to slice out of the source anymore, so the two
        assertions are checked against their own sources instead.
        """
        import inspect

        import routers.albums as albums_module

        handler_source = inspect.getsource(albums_module.get_album)
        assert "return serialize_album(album)" in handler_source

        factory_source = inspect.getsource(albums_module.create_albums_router)
        assert 'router.add_api_route("/api/albums/{album_id}", get_album' in factory_source
        assert "response_model=AlbumResponse" in factory_source.split(
            'router.add_api_route("/api/albums/{album_id}", get_album', 1
        )[1].split("\n", 1)[0]

    def test_emits_snake_case_only(self):
        album = self._make_album(track_count=2, total_duration=300.0)
        result = serialize_album(album)
        for camel in ('trackCount', 'artworkUrl', 'totalDuration', 'artistId', 'dateAdded'):
            assert camel not in result
        assert result['track_count'] == 2
        assert result['total_duration'] == 300.0
        assert result['artist_id'] == 7

    def test_carries_every_field_the_frontend_album_contract_declares(self):
        """`AlbumApiResponse` / `transformAlbum` must find each key it reads."""
        album = self._make_album(track_count=2, total_duration=300.0)
        result = serialize_album(album)
        for field in ('id', 'title', 'artist', 'artist_id', 'year',
                      'artwork_url', 'track_count', 'total_duration'):
            assert field in result, f"transformAlbum would read {field} as undefined"

    def test_does_not_advertise_a_genre_field(self):
        """Album has no genre column, so the response must not claim one (#4709).

        The deleted `AlbumDetailResponse` declared `genre` with a None default
        long after the serializer stopped emitting it, so the endpoint shipped
        a permanent `"genre": null`. `AlbumResponse` declares no such field.
        """
        from schemas import AlbumResponse

        assert 'genre' not in AlbumResponse.model_fields

    def test_created_at_is_the_creation_timestamp(self):
        """Album.to_dict() emits created_at, never date_added (#4709).

        The camelCase serializer spelled this `date_added or created_at`; the
        first operand could never be populated, so the fallback worked only by
        accident. The snake_case shape carries `created_at` directly.
        """
        album = self._make_album(extra={'created_at': '2020-01-02T03:04:05Z'})
        assert serialize_album(album)['created_at'] == '2020-01-02T03:04:05Z'


# ---------------------------------------------------------------------------
# serialize_artist — count derivation
# ---------------------------------------------------------------------------

class TestSerializeArtist:
    """#5084: album_count/track_count are computed by Artist.to_dict()
    (preferring the repository's SQL aggregates track_count_expr/
    album_count_expr, falling back to walking the collections only when the
    query didn't supply them) — NOT re-derived here. Same contract, and same
    reasoning, as TestSerializeAlbum above: ArtistRepository.get_all()/
    .search() no longer eager-load `tracks`/`albums`, and a real detached ORM
    instance raises DetachedInstanceError (not caught by `hasattr()`) on an
    unloaded relationship access."""

    def _make_artist(self, album_count=0, track_count=0, **attrs):
        dict_result = {
            'id': 5,
            'name': 'Artist C',
            'track_count': track_count,
            'album_count': album_count,
        }
        return _FakeModel(dict_result, **attrs)

    def test_album_count_passed_through_from_to_dict(self):
        artist = self._make_artist(album_count=3)
        result = serialize_artist(artist)
        assert result['album_count'] == 3

    def test_track_count_passed_through_from_to_dict(self):
        artist = self._make_artist(track_count=7)
        result = serialize_artist(artist)
        assert result['track_count'] == 7

    def test_counts_are_not_re_derived_from_the_collections(self):
        """to_dict()'s values win even when the collections disagree — the
        collections are exactly what the list query no longer loads."""
        artist = self._make_artist(
            album_count=3,
            track_count=7,
            albums=[object()],
            tracks=[object(), object()],
        )

        result = serialize_artist(artist)

        assert result['album_count'] == 3
        assert result['track_count'] == 7

    def test_serialize_artists_list(self):
        artists = [self._make_artist(album_count=i) for i in range(4)]
        results = [serialize_artist(a) for a in artists]
        assert len(results) == 4


# ---------------------------------------------------------------------------
# serialize_playlist — count derivation
# ---------------------------------------------------------------------------

class TestSerializePlaylist:
    """Playlist.to_dict() owns track_count/total_duration: the SQL aggregates
    when the query supplied them (#4554), else the guarded tracks read."""

    def _make_playlist(self, track_count=0):
        from auralis.library.models import Playlist, Track

        return Playlist(
            id=20, name='Chill Mix',
            tracks=[Track(duration=60.0) for _ in range(track_count)],
        )

    def test_track_count_derived_from_tracks(self):
        result = serialize_playlist(self._make_playlist(track_count=5))
        assert result['track_count'] == 5
        assert result['total_duration'] == 300.0

    def test_sql_aggregate_wins_over_the_tracks_collection(self):
        playlist = self._make_playlist(track_count=2)
        playlist.track_count_expr = 9
        playlist.total_duration_expr = 540.0
        result = serialize_playlist(playlist)
        assert result['track_count'] == 9
        assert result['total_duration'] == 540.0

    def test_serialize_playlists_list(self):
        playlists = [self._make_playlist(track_count=i) for i in range(3)]
        results = serialize_playlists(playlists)
        assert [r['track_count'] for r in results] == [0, 1, 2]

    def test_serialize_playlist_empty_tracks(self):
        result = serialize_playlist(self._make_playlist(track_count=0))
        assert result['track_count'] == 0
