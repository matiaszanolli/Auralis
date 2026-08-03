"""Shared safety limits for external artwork URLs and payloads."""

from urllib.parse import urlparse

# Keep external artwork responses bounded before parsing or persisting them.
MAX_ARTWORK_PAYLOAD_BYTES = 5 * 1024 * 1024


# Domains used by the artwork sources supported by ArtworkService and
# ArtworkDownloader. Exact hosts and their subdomains are accepted.
TRUSTED_ARTWORK_DOMAINS = frozenset({
    "mzstatic.com",
    "coverartarchive.org",
    "archive.org",
    "lastfm.freetls.fastly.net",
    "lastfm-img2.akamaized.net",
    "i.discogs.com",
    "img.discogs.com",
    "upload.wikimedia.org",
    "commons.wikimedia.org",
})


def validate_artwork_url(url: str) -> bool:
    """Return whether *url* uses HTTP(S) on a trusted artwork host."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http") or not parsed.hostname:
            return False

        hostname = parsed.hostname.lower()
        return any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in TRUSTED_ARTWORK_DOMAINS
        )
    except (TypeError, ValueError):
        return False
