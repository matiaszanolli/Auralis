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
    def _make_album(self, track_durations=None):
        dict_result = {
            'id': 10,
            'title': 'Album A',
            'artist': 'Artist B',
            'year': 2020,
            'artwork_path': None,
            'track_count': 0,
            'total_duration': 0,
        }
        if track_durations is not None:
            tracks = []
            for d in track_durations:
                t = types.SimpleNamespace(duration=d)
                tracks.append(t)
        else:
            tracks = None
        return _FakeModel(dict_result, tracks=tracks)

    def test_total_duration_summed_from_tracks(self):
        album = self._make_album(track_durations=[120.0, 180.0, 60.0])
        result = serialize_album(album)
        assert result['total_duration'] == 360.0

    def test_track_count_derived_from_tracks(self):
        album = self._make_album(track_durations=[100.0, 200.0])
        result = serialize_album(album)
        assert result['track_count'] == 2

    def test_total_duration_zero_when_no_tracks(self):
        album = self._make_album(track_durations=None)
        result = serialize_album(album)
        assert result['total_duration'] == 0

    def test_ignores_tracks_with_none_duration(self):
        album = self._make_album(track_durations=[100.0, None, 50.0])
        result = serialize_album(album)
        assert result['total_duration'] == 150.0

    def test_serialize_albums_list(self):
        albums = [self._make_album(track_durations=[60.0]) for _ in range(3)]
        results = serialize_albums(albums)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# serialize_artist — count derivation
# ---------------------------------------------------------------------------

class TestSerializeArtist:
    def _make_artist(self, album_count=0, track_count=0):
        dict_result = {'id': 5, 'name': 'Artist C', 'track_count': 0, 'album_count': 0}
        return _FakeModel(
            dict_result,
            albums=[object() for _ in range(album_count)],
            tracks=[object() for _ in range(track_count)],
        )

    def test_album_count_derived_from_albums(self):
        artist = self._make_artist(album_count=3)
        result = serialize_artist(artist)
        assert result['album_count'] == 3

    def test_track_count_derived_from_tracks(self):
        artist = self._make_artist(track_count=7)
        result = serialize_artist(artist)
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
