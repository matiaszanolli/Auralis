"""
Discogs artist-artwork provider
~~~~~~~~~~~~~~~~~~~~~~~

Split from ``ArtworkService`` (#6273); the service method stays a thin
delegator. The service is CLI-only (``auralis/cli/fetch_artwork.py``); the
web backend has its own stack under ``auralis-web/backend/services/``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

def fetch_from_discogs(service, self, artist_name: str) -> dict[str, Any] | None:
    """
    Fetch artist artwork from Discogs API.

    Requires service.discogs_token to be set.

    Args:
        artist_name: Artist name to search

    Returns:
        Dict with artwork_url and source, or None
    """
    if not service.discogs_token:
        return None

    try:
        # URL-encode artist name
        encoded_name = urllib.parse.quote(artist_name)

        # Search for artist — token sent as Authorization header, not URL param (fixes #2244)
        search_url = (
            f"https://api.discogs.com/database/search"
            f"?q={encoded_name}&type=artist"
        )

        req = urllib.request.Request(search_url)
        req.add_header('Authorization', f'Discogs token={service.discogs_token}')
        req.add_header('User-Agent', service.user_agent)

        with urllib.request.urlopen(req, timeout=service.timeout) as response:
            data = _read_json_response(response)

        results = data.get('results', [])
        if not results:
            return None

        # Get first result's image
        artist = results[0]
        image_url = artist.get('cover_image') or artist.get('thumb')

        if image_url:
            return _validated_artwork_result(image_url, "discogs")

        return None

    except Exception as e:
        logger.debug(f"Discogs fetch failed for {sanitize_log_value(artist_name)}: {e}")
        return None
