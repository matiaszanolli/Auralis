"""
Entity Serializers
~~~~~~~~~~~~~~~~~~

Per-entity serializers (track/album/artist/playlist) split from
serializers.py (#6271); the generic serialize_object machinery and the
DEFAULT_*_FIELDS maps stay there (tracked by open #5803).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from .serializers import (
    DEFAULT_ALBUM_FIELDS,
    DEFAULT_ARTIST_FIELDS,
    DEFAULT_PLAYLIST_FIELDS,
    DEFAULT_TRACK_FIELDS,
    serialize_object,
    serialize_objects,
)


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
