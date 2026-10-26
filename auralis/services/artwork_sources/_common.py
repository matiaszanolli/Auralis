"""
Shared helpers for the artwork metadata providers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bounded JSON decoding and trusted-URL validation used by the MusicBrainz,
Discogs and Last.fm fetchers (split from ``artwork_service`` with them, #6273).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
import logging
from typing import Any

from auralis.utils.artwork_security import (
    MAX_ARTWORK_PAYLOAD_BYTES,
    validate_artwork_url,
)

logger = logging.getLogger(__name__)


def _read_json_response(response: Any) -> Any:
    """Decode a bounded JSON response from an artwork metadata provider."""
    payload = response.read(MAX_ARTWORK_PAYLOAD_BYTES + 1)
    if len(payload) > MAX_ARTWORK_PAYLOAD_BYTES:
        raise ValueError(
            f"Artwork metadata response exceeded {MAX_ARTWORK_PAYLOAD_BYTES} bytes"
        )
    return json.loads(payload.decode("utf-8"))


def _validated_artwork_result(
    artwork_url: str,
    source: str,
) -> dict[str, str] | None:
    """Build an artwork result only when its external URL is trusted."""
    if not validate_artwork_url(artwork_url):
        logger.warning("Rejecting untrusted %s artwork URL: %r", source, artwork_url)
        return None
    return {"artwork_url": artwork_url, "source": source}
