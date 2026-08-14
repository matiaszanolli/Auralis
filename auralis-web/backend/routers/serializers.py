"""
Object serialization utilities for consistent API responses.

This module provides centralized functions for converting database objects to
dictionaries for JSON serialization, with fallback handling and validation.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# getattr-fallback defaults — NOT the response contract (#4708)
#
# `serialize_object()` returns `obj.to_dict()` for any non-Mock object that
# provides one, so for a real ORM row these maps are never consulted. They are
# reached only by:
#   * Mock/MagicMock objects in tests (the branch is explicitly skipped for
#     them so a Mock's auto-generated `to_dict` cannot recurse), and
#   * the rare case where a real `to_dict()` raises, which is logged and
#     falls through.
#
# Do not read a key here as a guarantee about what an endpoint emits. The
# comments below used to say things like "always required by
# TrackApiResponse" and cite #2267 / #2851 as though this code enforced them;
# it cannot, and that misreading is what let `Track.to_dict()`'s field gaps and
# the album-detail casing bugs sit unnoticed (#4708).
#
# The actual response contract is the union of `Model.to_dict()` and these
# defaults, declared as Pydantic models in `schemas.py` (see the "Library
# Domain Response Models" block there for why it must be the union) and pinned
# mechanically by `tests/backend/test_response_model_coverage.py`. These maps
# keep their names because that union test and the response models depend on
# them — they are a real, if rarely-taken, path rather than test-only fixtures.
#
# Where a key below has no counterpart in the corresponding `to_dict()`, the
# two paths genuinely disagree; the union above is what reconciles them.
# ---------------------------------------------------------------------------
DEFAULT_TRACK_FIELDS = {
    # Core identity. `Track.to_dict()` emits all five.
    'id': None,
    'title': 'Unknown',
    # `artist` (singular) is fallback-only — to_dict() emits `artists` (list).
    'artist': '',
    'album': '',
    'duration': 0,
    # NOTE: `filepath` is deliberately absent. #3205 made the server-side path
    # server-only (player_state.TrackInfo marks it Field(exclude=True)), and
    # Track.to_dict() — which serialize_object() prefers whenever the object
    # provides it — omits it too. Listing it here only affected the getattr
    # fallback (Mocks and detached objects), so the two paths disagreed about
    # whether a serialized track carries a path at all (#4586).
    'format': 'Unknown',
    # Optional metadata. #2267 wanted artist/album on the wire; that is
    # delivered by Track.to_dict(), not here. Fallback-only keys in this
    # group — to_dict() emits none of them: `genre` (it emits `genres`, a
    # list), `loudness` (it emits `lufs_level`), `date_added`/`date_modified`
    # (it emits `created_at`/`updated_at`).
    'artwork_url': None,
    'genre': None,
    'year': None,
    'bitrate': None,
    'sample_rate': None,
    'bit_depth': None,
    'loudness': None,
    'date_added': None,
    'date_modified': None,
    # Navigation and favorites. #2851 added these to the wire via
    # Track.to_dict(), which emits all four; they are mirrored here so the
    # fallback shape does not lose them.
    'album_id': None,
    'track_number': None,
    'disc_number': None,
    'favorite': False,
}

DEFAULT_ALBUM_FIELDS = {
    'id': None,
    'title': 'Unknown Album',
    'artist': 'Unknown Artist',
    'year': None,
    'artwork_url': None,
    'track_count': 0,
    'total_duration': 0
}

DEFAULT_ARTIST_FIELDS = {
    'id': None,
    'name': 'Unknown Artist',
    'track_count': 0,
    'album_count': 0,
    # Artwork fields mirrored here so the fallback shape matches
    # Artist.to_dict(), which also emits them (#2511).
    'artwork_url': None,
    'artwork_source': None,
}

DEFAULT_PLAYLIST_FIELDS = {
    'id': None,
    'name': 'Untitled Playlist',
    'track_count': 0,
    'is_smart': False,
    'smart_criteria': None,
    'created_at': None,
    'updated_at': None
}


def serialize_object(obj: Any, fallback_fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Serialize a single object to a dictionary.

    Returns ``obj.to_dict()`` whenever the object provides one and is not a
    Mock — which is every real ORM row — and only otherwise projects ``obj``
    through ``fallback_fields`` with getattr.

    ``fallback_fields`` therefore does NOT describe what an endpoint returns
    for a real row; see the block comment above ``DEFAULT_TRACK_FIELDS`` and
    the response models in ``schemas.py`` for the actual contract (#4708).

    Args:
        obj: Object to serialize
        fallback_fields: Defaults used only on the getattr path (Mocks, or a
            real object whose to_dict() raised)

    Returns:
        Dictionary representation of the object

    Example:
        # Real row -> Track.to_dict(); the fallback map is not consulted.
        data = serialize_object(track, DEFAULT_TRACK_FIELDS)
    """
    if obj is None:
        return {}

    # Prefer object's to_dict method (but not for Mock objects in tests)
    if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict', None)):
        # Skip Mock objects to avoid circular reference issues
        obj_type_name = type(obj).__name__
        if 'Mock' not in obj_type_name and 'MagicMock' not in obj_type_name:
            try:
                result = obj.to_dict()
                if isinstance(result, dict):
                    return result
            except Exception as e:
                logger.warning(f"Error calling to_dict on {obj_type_name}: {e}")

    # Fall back to getattr with defaults
    if fallback_fields is None:
        fallback_fields = {}

    result = {}
    for field, default in fallback_fields.items():
        value = getattr(obj, field, default)
        # Sanitize relationship objects (ORM models / Mocks) that aren't
        # directly JSON-serializable.  Real objects normally go through
        # to_dict() above; this only fires for the fallback path.
        if value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
            if hasattr(value, 'name') and isinstance(getattr(value, 'name', None), str):
                value = value.name
            elif hasattr(value, 'title') and isinstance(getattr(value, 'title', None), str):
                value = value.title
            else:
                value = default
        result[field] = value
    return result


def serialize_objects(
    objects: list[Any],
    fallback_fields: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Serialize a list of objects to dictionaries.

    Args:
        objects: List of objects to serialize
        fallback_fields: Dictionary mapping field names to default values if object lacks the field

    Returns:
        List of dictionaries

    Example:
        tracks = [track1, track2, track3]
        data = serialize_objects(tracks, DEFAULT_TRACK_FIELDS)
    """
    return [serialize_object(obj, fallback_fields) for obj in objects]


def serialize_track(track: Any) -> dict[str, Any]:
    """
    Serialize a track object with default Track fields.

    Args:
        track: Track object to serialize

    Returns:
        Dictionary representation of the track
    """
    return serialize_object(track, DEFAULT_TRACK_FIELDS)


def serialize_tracks(tracks: list[Any]) -> list[dict[str, Any]]:
    """
    Serialize a list of tracks with default Track fields.

    Args:
        tracks: List of track objects to serialize

    Returns:
        List of track dictionaries
    """
    return serialize_objects(tracks, DEFAULT_TRACK_FIELDS)


def serialize_album(album: Any) -> dict[str, Any]:
    """
    Serialize an album object with duration calculation.

    Args:
        album: Album object to serialize

    Returns:
        Dictionary representation of the album with total_duration calculated
    """
    album_dict = serialize_object(album, DEFAULT_ALBUM_FIELDS)

    # Sanitize artwork_url: the fallback getattr path returns a raw filesystem
    # path (e.g. /home/user/.auralis/artwork/album5.jpg) instead of an API URL.
    # Convert it here so internal paths are never leaked to the frontend (fixes #2270).
    raw_artwork = album_dict.get('artwork_url')
    if raw_artwork and not str(raw_artwork).startswith('/api/'):
        album_id = album_dict.get('id') or getattr(album, 'id', None)
        album_dict['artwork_url'] = f"/api/albums/{album_id}/artwork" if album_id else None

    # track_count/total_duration come from Album.to_dict() above (#4777),
    # which prefers the repository's SQL-computed aggregates
    # (track_count_expr/total_duration_expr) when the query supplied them,
    # falling back to walking `tracks` only when it didn't. This function
    # used to re-derive both by reading `album.tracks` directly here too —
    # but AlbumRepository.get_all()/.search()/.get_recent() no longer
    # eager-load that collection (it would defeat the point of the SQL
    # aggregates), and `hasattr(album, 'tracks')` does NOT guard against the
    # DetachedInstanceError a real ORM instance raises on an unloaded
    # relationship (DetachedInstanceError is not an AttributeError, so
    # hasattr() lets it propagate) — touching `album.tracks` here would
    # crash the endpoint the moment that eager-load was dropped.
    return album_dict


def serialize_album_detail(album: Any) -> dict[str, Any]:
    """Serialize an album to the frontend camelCase domain shape (#4423).

    ``GET /api/albums/{id}`` is consumed on the camelCase convention (the
    ``Album`` domain type / albumTransformer contract), so this maps the
    snake_case ``serialize_album`` output to camelCase keys rather than leaking
    ``track_count``/``artwork_url``. Kept distinct from the sibling
    ``{id}/tracks`` endpoint, which stays snake_case for its existing consumer.
    """
    snake = serialize_album(album)
    return {
        'id': snake.get('id'),
        'title': snake.get('title'),
        'artist': snake.get('artist'),
        'artistId': snake.get('artist_id'),
        'year': snake.get('year'),
        'artworkUrl': snake.get('artwork_url'),
        'genre': snake.get('genre'),
        'trackCount': snake.get('track_count', 0),
        'totalDuration': snake.get('total_duration', 0),
        'dateAdded': snake.get('date_added') or snake.get('created_at'),
    }


def serialize_albums(albums: list[Any]) -> list[dict[str, Any]]:
    """
    Serialize a list of albums with duration calculation.

    Args:
        albums: List of album objects to serialize

    Returns:
        List of album dictionaries
    """
    return [serialize_album(album) for album in albums]


def serialize_artist(artist: Any) -> dict[str, Any]:
    """
    Serialize an artist object with default Artist fields.

    Args:
        artist: Artist object to serialize

    Returns:
        Dictionary representation of the artist
    """
    artist_dict = serialize_object(artist, DEFAULT_ARTIST_FIELDS)

    # album_count/track_count come from Artist.to_dict() above (#5084), which
    # prefers the repository's SQL-computed aggregates (track_count_expr/
    # album_count_expr) when the query supplied them and falls back to walking
    # the collections when it did not. This function used to re-derive both by
    # reading artist.albums/artist.tracks here — but ArtistRepository's list
    # reads no longer eager-load them (that was the whole point), and
    # `hasattr(artist, 'tracks')` does NOT guard against the
    # DetachedInstanceError a real ORM instance raises on an unloaded
    # relationship (DetachedInstanceError is not an AttributeError, so
    # hasattr() lets it propagate). This mirrors serialize_album, which lost
    # the same block for the same reason in #4777.
    #
    # The Mock-object path is unaffected: serialize_object() falls back to
    # getattr over DEFAULT_ARTIST_FIELDS, which already carries
    # album_count/track_count defaults.
    return artist_dict


def serialize_artists(artists: list[Any]) -> list[dict[str, Any]]:
    """
    Serialize a list of artists with default Artist fields.

    Args:
        artists: List of artist objects to serialize

    Returns:
        List of artist dictionaries
    """
    return [serialize_artist(artist) for artist in artists]


def serialize_playlist(playlist: Any) -> dict[str, Any]:
    """
    Serialize a playlist object with default Playlist fields.

    Args:
        playlist: Playlist object to serialize

    Returns:
        Dictionary representation of the playlist
    """
    playlist_dict = serialize_object(playlist, DEFAULT_PLAYLIST_FIELDS)

    # Prefer the SQL-computed count when the query asked for it (#4554).
    # PlaylistRepository.get_all() populates track_count_expr with a correlated
    # COUNT so a list view never has to materialise the tracks collection.
    sql_count = getattr(playlist, 'track_count_expr', None)
    if isinstance(sql_count, int):
        playlist_dict['track_count'] = sql_count
        return playlist_dict

    # Otherwise fall back to counting the loaded tracks. try/except guards
    # against Mock objects in tests, whose .tracks is itself an auto-generated
    # Mock (truthy, but not sized) — same pattern as serialize_album's guard
    # (#4306) — and against a detached playlist whose tracks were never loaded,
    # where the lazy load raises rather than returning empty.
    try:
        if getattr(playlist, 'tracks', None):
            playlist_dict['track_count'] = len(playlist.tracks)
    except (TypeError, SQLAlchemyError):
        pass

    return playlist_dict


def serialize_playlists(playlists: list[Any]) -> list[dict[str, Any]]:
    """
    Serialize a list of playlists with default Playlist fields.

    Args:
        playlists: List of playlist objects to serialize

    Returns:
        List of playlist dictionaries
    """
    return [serialize_playlist(playlist) for playlist in playlists]
