"""
Entity Serializers
~~~~~~~~~~~~~~~~~~

Per-entity serializers (track/album/artist/playlist) split from
serializers.py (#6271); the generic serialize_object stays there.

Each row's ``to_dict()`` owns its response shape, including the derived
fields the list views depend on, so these stay thin:

* ``Album.to_dict()`` / ``Artist.to_dict()`` / ``Playlist.to_dict()`` prefer
  the repository's SQL-computed aggregates (``track_count_expr`` etc.,
  #4777 / #5084 / #4554) and otherwise count through the guarded
  ``_safe_collection()`` read. Re-deriving a count here from ``album.tracks``
  would raise ``DetachedInstanceError`` (not an ``AttributeError``, so
  ``hasattr()`` does not guard it) now that the list reads no longer
  eager-load those collections.
* ``Album.to_dict()`` emits ``artwork_url`` as an ``/api/albums/<id>/artwork``
  URL, never the filesystem path (#2270).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from .serializers import serialize_object, serialize_objects


def serialize_tracks(tracks: list[Any]) -> list[dict[str, Any]]:
    """Serialize a list of tracks."""
    return serialize_objects(tracks)


def serialize_album(album: Any) -> dict[str, Any]:
    """Serialize an album object."""
    return serialize_object(album)


def serialize_albums(albums: list[Any]) -> list[dict[str, Any]]:
    """Serialize a list of albums."""
    return serialize_objects(albums)


def serialize_artist(artist: Any) -> dict[str, Any]:
    """Serialize an artist object."""
    return serialize_object(artist)


def serialize_playlist(playlist: Any) -> dict[str, Any]:
    """Serialize a playlist object."""
    return serialize_object(playlist)


def serialize_playlists(playlists: list[Any]) -> list[dict[str, Any]]:
    """Serialize a list of playlists."""
    return serialize_objects(playlists)
