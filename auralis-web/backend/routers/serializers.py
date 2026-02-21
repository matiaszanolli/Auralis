"""
Object serialization utilities for consistent API responses.

This module provides centralized functions for converting database objects to
dictionaries for JSON serialization, with fallback handling and validation.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Default field mappings for common objects
DEFAULT_TRACK_FIELDS = {
    # Core identity (always required by TrackApiResponse)
    'id': None,
    'title': 'Unknown',
    'artist': '',
    'album': '',
    'duration': 0,
    'filepath': '',
    'format': 'Unknown',
    # Optional metadata (fixes #2267 — frontend requires artist/album, others desirable)
    'artwork_url': None,
    'genre': None,
    'year': None,
    'bitrate': None,
    'sample_rate': None,
    'bit_depth': None,
    'loudness': None,
    'date_added': None,
    'date_modified': None,
}

DEFAULT_ALBUM_FIELDS = {
    'id': None,
    'title': 'Unknown Album',
    'artist': 'Unknown Artist',
    'year': None,
    'artwork_path': None,
    'track_count': 0,
    'total_duration': 0
}

DEFAULT_ARTIST_FIELDS = {
    'id': None,
    'name': 'Unknown Artist',
    'track_count': 0,
    'album_count': 0
}

DEFAULT_PLAYLIST_FIELDS = {
    'id': None,
    'name': 'Untitled Playlist',
    'track_count': 0,
    'created_at': None,
    'updated_at': None
}


def serialize_object(obj: Any, fallback_fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Serialize a single object to a dictionary.

    Attempts to use the object's to_dict() method if available, otherwise falls back
    to getattr with provided default values.

    Args:
        obj: Object to serialize
        fallback_fields: Dictionary mapping field names to default values if object lacks the field

    Returns:
        Dictionary representation of the object

    Example:
        track = Track(id=1, title="Song", duration=180)
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

    return {
        field: getattr(obj, field, default)
        for field, default in fallback_fields.items()
    }


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

    # Calculate total_duration from tracks if available
    if hasattr(album, 'tracks') and album.tracks:
        try:
            total_duration = sum(
                track.duration for track in album.tracks
                if hasattr(track, 'duration') and track.duration is not None
            )
            album_dict['total_duration'] = total_duration
        except (AttributeError, TypeError):
            # Handle cases where tracks might not have duration or other issues
            album_dict['total_duration'] = album_dict.get('total_duration', 0)
    else:
        album_dict['total_duration'] = album_dict.get('total_duration', 0)

    # Set track_count if not already in dict
    if 'track_count' not in album_dict or album_dict['track_count'] == 0:
        try:
            album_dict['track_count'] = len(album.tracks) if hasattr(album, 'tracks') else 0
        except TypeError:
            album_dict['track_count'] = 0

    return album_dict


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

    # Calculate counts from related objects if available
    if hasattr(artist, 'albums') and artist.albums:
        artist_dict['album_count'] = len(artist.albums)
    if hasattr(artist, 'tracks') and artist.tracks:
        artist_dict['track_count'] = len(artist.tracks)

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

    # Calculate track_count from tracks if available
    if hasattr(playlist, 'tracks') and playlist.tracks:
        playlist_dict['track_count'] = len(playlist.tracks)

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
