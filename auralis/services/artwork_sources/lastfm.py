"""
Last.fm artist-artwork provider
~~~~~~~~~~~~~~~~~~~~~~~

Split from ``ArtworkService`` (#6273); the service method stays a thin
delegator. The service is CLI-only (``auralis/cli/fetch_artwork.py``); the
web backend has its own stack under ``auralis-web/backend/services/``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

def fetch_from_lastfm(service, self, artist_name: str) -> dict[str, Any] | None:
    """
    Fetch artist artwork from Last.fm API.

    Requires service.lastfm_api_key to be set.

    Args:
        artist_name: Artist name to search

    Returns:
        Dict with artwork_url and source, or None
    """
    if not service.lastfm_api_key:
        return None

    try:
        # URL-encode artist name
        encoded_name = urllib.parse.quote(artist_name)

        # Get artist info
        info_url = (
            f"https://ws.audioscrobbler.com/2.0/"
            f"?method=artist.getinfo&artist={encoded_name}"
            f"&api_key={service.lastfm_api_key}&format=json"
        )

        req = urllib.request.Request(info_url)
        req.add_header('User-Agent', service.user_agent)

        with urllib.request.urlopen(req, timeout=service.timeout) as response:
            data = _read_json_response(response)

        artist = data.get('artist', {})
        images = artist.get('image', [])

        # Get largest image
        for img in reversed(images):  # Reverse to get largest first
            url = img.get('#text')
            if url:
                result = _validated_artwork_result(url, "lastfm")
                if result:
                    return result

        return None

    except Exception as e:
        logger.debug(f"Last.fm fetch failed for {sanitize_log_value(artist_name)}: {e}")
        return None
