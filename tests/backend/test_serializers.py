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

from routers.serializers import (
    DEFAULT_ALBUM_FIELDS,
    DEFAULT_ARTIST_FIELDS,
    DEFAULT_PLAYLIST_FIELDS,
    DEFAULT_TRACK_FIELDS,
    serialize_album,
    serialize_album_detail,
    serialize_albums,
    serialize_artist,
    serialize_artists,
    serialize_object,
    serialize_objects,
    serialize_playlist,
    serialize_playlists,
    serialize_track,
    serialize_tracks,
)


# ---------------------------------------------------------------------------
# Helper: real Python object with to_dict() (not a Mock)
# serialize_object skips to_dict() on Mock/MagicMock to avoid circular refs,
# so tests that need to_dict() must use real objects.
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
# DEFAULT_TRACK_FIELDS — sensitive field exclusion
# ---------------------------------------------------------------------------

class TestDefaultTrackFields:
    def test_filepath_not_in_default_track_fields(self):
        assert 'filepath' not in DEFAULT_TRACK_FIELDS

    def test_required_safe_fields_present(self):
        assert 'id' in DEFAULT_TRACK_FIELDS
        assert 'title' in DEFAULT_TRACK_FIELDS
        assert 'duration' in DEFAULT_TRACK_FIELDS
        assert 'format' in DEFAULT_TRACK_FIELDS

    def test_default_id_is_none(self):
        assert DEFAULT_TRACK_FIELDS['id'] is None

    def test_default_title_is_unknown(self):
        assert DEFAULT_TRACK_FIELDS['title'] == 'Unknown'

    def test_default_duration_is_zero(self):
        assert DEFAULT_TRACK_FIELDS['duration'] == 0


# ---------------------------------------------------------------------------
# serialize_object — to_dict preference and fallback
# ---------------------------------------------------------------------------

class TestSerializeObject:
    def test_uses_to_dict_when_available(self):
        obj = _FakeModel({"id": 42, "title": "Song"})
        result = serialize_object(obj)
        assert result == {"id": 42, "title": "Song"}

    def test_falls_back_to_getattr_when_no_to_dict(self):
        obj = Mock(spec=[])  # no to_dict attribute
        obj.id = 7
        obj.title = "Fallback"
        result = serialize_object(obj, {'id': None, 'title': 'Unknown'})
        assert result['id'] == 7
        assert result['title'] == "Fallback"

    def test_uses_fallback_default_for_missing_attr(self):
        obj = Mock(spec=[])  # no attributes
        result = serialize_object(obj, {'id': None, 'duration': 0})
        assert result['id'] is None
        assert result['duration'] == 0

    def test_returns_empty_dict_for_none(self):
        result = serialize_object(None)
        assert result == {}

    def test_skips_to_dict_for_mock_objects(self):
        """Mock objects must not use to_dict (circular reference risk)."""
        mock_obj = MagicMock()
        mock_obj.id = 1
        mock_obj.title = "Mock Track"
        # serialize_object should NOT call to_dict on a MagicMock
        result = serialize_object(mock_obj, {'id': None, 'title': 'Unknown'})
        assert result['id'] == 1

    def test_falls_back_when_to_dict_raises(self):
        class _BrokenModel:
            id = 5
            def to_dict(self):
                raise Exception("detached session")

        result = serialize_object(_BrokenModel(), {'id': None})
        assert result['id'] == 5

    def test_empty_fallback_fields_returns_empty_dict(self):
        obj = Mock(spec=[])
        result = serialize_object(obj, {})
        assert result == {}


# ---------------------------------------------------------------------------
# serialize_track / serialize_tracks — sensitive field exclusion
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
        result = serialize_track(track)
        assert 'filepath' not in result

    def test_safe_fields_present(self):
        track = self._make_track()
        result = serialize_track(track)
        assert result['id'] == 1
        assert result['title'] == 'Test Track'

    def test_fallback_does_not_include_filepath(self):
        """Fallback path (no to_dict) must also exclude filepath."""
        obj = Mock(spec=['id', 'title', 'duration', 'format'])
        obj.id = 2
        obj.title = "Fallback Track"
        obj.duration = 200.0
        obj.format = "MP3"
        result = serialize_track(obj)
        assert 'filepath' not in result

    def test_serialize_tracks_list(self):
        tracks = [self._make_track(id=i) for i in range(3)]
        results = serialize_tracks(tracks)
        assert len(results) == 3
        for r in results:
            assert 'filepath' not in r

    def test_serialize_tracks_empty_list(self):
        assert serialize_tracks([]) == []

    def test_serialize_objects_delegates_to_serialize_object(self):
        objs = [Mock(spec=[]), Mock(spec=[])]
        results = serialize_objects(objs, {'id': None})
        assert len(results) == 2


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


class TestSerializeAlbumDetail:
    """GET /api/albums/{id} camelCase contract (#4423)."""

    def _make_album(self, extra=None, track_count: int = 0, total_duration: float = 0):
        # Mirrors Album.to_dict()'s real key set. It deliberately carries NO
        # 'genre': Album has no genre column, so the old fixture's
        # `'genre': 'Rock'` was a key production can never emit — and it is
        # why serialize_album_detail's phantom genre mapping went unnoticed
        # (#4709, same shape as #4830/#4833).
        dict_result = {
            'id': 10,
            'title': 'Album A',
            'artist': 'Artist B',
            'artist_id': 7,
            'year': 2020,
            'artwork_path': None,
            'track_count': track_count,
            'total_duration': total_duration,
        }
        if extra:
            dict_result.update(extra)
        return _FakeModel(dict_result)

    def test_returns_camelcase_domain_keys(self):
        album = self._make_album(track_count=2, total_duration=300.0)
        result = serialize_album_detail(album)
        # Matches the frontend Album domain / albumTransformer output.
        assert result == {
            'id': 10,
            'title': 'Album A',
            'artist': 'Artist B',
            'artistId': 7,
            'year': 2020,
            'artworkUrl': None,
            'trackCount': 2,
            'totalDuration': 300.0,
            'dateAdded': None,
        }

    def test_does_not_advertise_a_genre_field(self):
        """Album has no genre column, so the response must not claim one (#4709).

        Even when the serialized album somehow carries a `genre` key, it must
        not reach the camelCase detail response — the frontend Album type no
        longer declares it either.
        """
        album = self._make_album(extra={'genre': 'Rock'})
        assert 'genre' not in serialize_album_detail(album)

    def test_never_leaks_snake_case_keys(self):
        album = self._make_album(track_count=1, total_duration=60.0)
        result = serialize_album_detail(album)
        for snake in ('track_count', 'artwork_url', 'total_duration', 'artist_id', 'album_id'):
            assert snake not in result

    def test_date_added_reads_created_at(self):
        """Album.to_dict() emits created_at, never date_added (#4709).

        This used to be spelled `date_added or created_at`; the first operand
        could never be populated, so the fallback worked only by accident.
        """
        album = self._make_album(extra={'created_at': '2020-01-02T03:04:05Z'})
        result = serialize_album_detail(album)
        assert result['dateAdded'] == '2020-01-02T03:04:05Z'


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
        results = serialize_artists(artists)
        assert len(results) == 4


# ---------------------------------------------------------------------------
# serialize_playlist — count derivation
# ---------------------------------------------------------------------------

class TestSerializePlaylist:
    def _make_playlist(self, track_count=0):
        dict_result = {'id': 20, 'name': 'Chill Mix', 'track_count': 0, 'created_at': None, 'updated_at': None}
        return _FakeModel(dict_result, tracks=[object() for _ in range(track_count)])

    def test_track_count_derived_from_tracks(self):
        playlist = self._make_playlist(track_count=5)
        result = serialize_playlist(playlist)
        assert result['track_count'] == 5

    def test_serialize_playlists_list(self):
        playlists = [self._make_playlist(track_count=i) for i in range(3)]
        results = serialize_playlists(playlists)
        assert len(results) == 3

    def test_serialize_playlist_empty_tracks(self):
        playlist = self._make_playlist(track_count=0)
        result = serialize_playlist(playlist)
        assert result['track_count'] == 0
