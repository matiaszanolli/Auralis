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
    """Return whether *url* uses HTTPS on a trusted artwork host.

    Plaintext ``http`` is refused even for a trusted host (#5337). Every URL
    Auralis builds itself is ``https``; the ones it does not build (API
    response fields, redirect targets) are exactly where an on-path attacker
    could downgrade the scheme to read or swap the image.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False

        hostname = parsed.hostname.lower()
        return any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in TRUSTED_ARTWORK_DOMAINS
        )
    except (TypeError, ValueError):
        return False


def detect_image_extension(data: bytes, default: str = "jpg") -> str:
    """Pick a file extension (without a leading dot) from an image's magic bytes.

    Both artwork write paths — online downloads (``artwork_downloader.py``)
    and embedded/folder extraction (``library/artwork.py``) — used to trust a
    caller-supplied label (a requested format, or a tag's declared MIME) when
    naming the saved file. Cover Art Archive/iTunes can return PNG/WebP for a
    JPEG request, and ID3/FLAC picture tags can declare GIF/WebP MIME types;
    either way the GET endpoint infers ``Content-Type`` from the extension, so
    a mislabelled file is served with the wrong Content-Type (#4419, #4849).
    Sniffing the real bytes here is shared so both write paths stay in sync.
    Falls back to ``default`` for unrecognised bytes.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return default


# Longest allowed side for stored artwork, shared by both write paths (#4439,
# #5522): a highly-compressible PNG can be far under the payload cap while
# having an enormous pixel size, and the un-parameterised GET serves the file
# at full resolution.
MAX_ARTWORK_DIMENSION = 2048


def bound_artwork_dimensions(data: bytes) -> bytes:
    """Downscale artwork whose largest side exceeds MAX_ARTWORK_DIMENSION.

    Shared by both artwork write paths (#5522): online downloads
    (``auralis-web/backend/services/artwork_downloader.py``) and
    embedded/folder extraction (``auralis/library/artwork.py``). Bounds
    oversized images so they are neither stored nor later streamed at full
    resolution. Best-effort: any failure (Pillow missing, unsupported or
    corrupt image) returns the original bytes unchanged so artwork is never
    dropped.

    Args:
        data: Raw image bytes.

    Returns:
        Downscaled image bytes, or the original bytes if no resize was needed
        or possible.
    """
    import io

    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as image:
            if max(image.size) <= MAX_ARTWORK_DIMENSION:
                return data
            # thumbnail() preserves aspect ratio and only ever downsizes.
            image.thumbnail((MAX_ARTWORK_DIMENSION, MAX_ARTWORK_DIMENSION))
            # Re-encode in the format Pillow itself detected rather than a
            # caller-supplied extension (#4849) — forcing every non-PNG
            # format to JPEG here silently produced JPEG bytes under a
            # .webp/.gif filename whenever a large WebP/GIF cover needed
            # downscaling, reproducing the Content-Type mismatch for exactly
            # the oversized case.
            fmt = image.format or "JPEG"
            if fmt == "JPEG" and image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format=fmt)
            return buffer.getvalue()
    except Exception:
        return data
