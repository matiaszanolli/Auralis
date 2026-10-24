"""
Object serialization utilities for consistent API responses.

This module provides centralized functions for converting database objects to
dictionaries for JSON serialization, with fallback handling and validation.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# getattr-fallback defaults — NOT the response contract (#4708)
#
# `serialize_object()` returns `obj.to_dict()` whenever it yields a dict, so for
# a real ORM row these maps are never consulted. They are reached only by:
#   * objects without a usable `to_dict()` -- chiefly the Mock/MagicMock rows
#     tests pass in, whose auto-generated `to_dict()` returns a Mock, not a
#     dict, and
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

    Returns ``obj.to_dict()`` whenever the object provides one and it returns a
    dict — which is every real ORM row — and only otherwise projects ``obj``
    through ``fallback_fields`` with getattr.

    ``fallback_fields`` therefore does NOT describe what an endpoint returns
    for a real row; see the block comment above ``DEFAULT_TRACK_FIELDS`` and
    the response models in ``schemas.py`` for the actual contract (#4708).

    Args:
        obj: Object to serialize
        fallback_fields: Defaults used only on the getattr path (an object with
            no usable to_dict(), or a real one whose to_dict() raised)

    Returns:
        Dictionary representation of the object

    Example:
        # Real row -> Track.to_dict(); the fallback map is not consulted.
        data = serialize_object(track, DEFAULT_TRACK_FIELDS)
    """
    if obj is None:
        return {}

    # Prefer the object's own to_dict(). Nothing here looks at the object's
    # type name (#5803): this used to skip any class whose name contained
    # "Mock", so production behaviour depended on how a test double was named.
    # It never needed to -- a Mock's auto-generated to_dict() returns another
    # Mock, which fails the isinstance(dict) check below and falls through to
    # the getattr path all the same.
    if callable(getattr(obj, 'to_dict', None)):
        try:
            result = obj.to_dict()
            if isinstance(result, dict):
                return result
        except Exception as e:
            logger.warning(f"Error calling to_dict on {type(obj).__name__}: {e}")

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
