"""
MusicBrainz artist-artwork provider
~~~~~~~~~~~~~~~~~~~~~~~

Split from ``ArtworkService`` (#6273); the service method stays a thin
delegator. The service is CLI-only (``auralis/cli/fetch_artwork.py``); the
web backend has its own stack under ``auralis-web/backend/services/``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING, Any

from auralis.utils.logging import sanitize_log_value

from ._common import _read_json_response, _validated_artwork_result

if TYPE_CHECKING:
    from ..artwork_service import ArtworkService

logger = logging.getLogger(__name__)


def _first_trusted_image(relations: list[dict[str, Any]]) -> dict[str, str] | None:
    """First 'image' relation whose URL passes the trusted-host check."""
    for relation in relations:
        if relation.get('type') != 'image':
            continue
        image_url = relation.get('url', {}).get('resource')
        if not image_url:
            continue
        result = _validated_artwork_result(image_url, "musicbrainz")
        if result:
            return result
    return None


def fetch_from_musicbrainz(service: "ArtworkService", artist_name: str) -> dict[str, Any] | None:
    """
    Fetch artist artwork from MusicBrainz.

    Steps:
    1. Search for artist by name to get MBID
    2. Get artist relations to find image URLs
    3. Return highest quality image

    Args:
        artist_name: Artist name to search

    Returns:
        Dict with artwork_url and source, or None
    """
    try:
        # URL-encode artist name
        encoded_name = urllib.parse.quote(artist_name)

        # Search for artist
        search_url = (
            f"https://musicbrainz.org/ws/2/artist/"
            f"?query=artist:{encoded_name}&fmt=json&limit=1"
        )

        req = urllib.request.Request(search_url)
        req.add_header('User-Agent', service.user_agent)

        with urllib.request.urlopen(req, timeout=service.timeout) as response:
            data = _read_json_response(response)

        if not data.get('artists') or len(data['artists']) == 0:
            return None

        artist = data['artists'][0]
        mbid = artist.get('id')

        if not mbid:
            return None

        # Get artist relations to find images
        relations_url = (
            f"https://musicbrainz.org/ws/2/artist/{mbid}"
            f"?inc=url-rels&fmt=json"
        )

        req = urllib.request.Request(relations_url)
        req.add_header('User-Agent', service.user_agent)

        with urllib.request.urlopen(req, timeout=service.timeout) as response:
            relations_data = _read_json_response(response)

        # Look for image URLs in relations
        return _first_trusted_image(relations_data.get('relations', []))

    except Exception as e:
        logger.debug(f"MusicBrainz fetch failed for {sanitize_log_value(artist_name)}: {e}")
        return None
