"""
Regression: downloaded artwork is bounded to the shared dimension cap (#5522)

#4439 added a 2048px downscale to the embedded/folder extraction path only.
The online-download writer kept a bare ``write_bytes`` — and the 5 MiB
payload cap does not bound pixel size (a large flat-colour PNG is tiny in
bytes), so the un-parameterised ``GET /api/albums/{id}/artwork`` streamed a
potentially enormous bitmap at full resolution. Both write paths now share
``auralis.utils.artwork_security.bound_artwork_dimensions``.
"""

import asyncio
import io
import sys
from pathlib import Path

from PIL import Image

from auralis.utils.artwork_security import (
    MAX_ARTWORK_DIMENSION,
    bound_artwork_dimensions,
)

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.artwork_downloader import ArtworkDownloader


def _png_bytes(width: int, height: int) -> bytes:
    """A highly-compressible flat-colour PNG of the given size."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (120, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_shared_helper_downscales_oversized_image():
    data = _png_bytes(8000, 8000)
    assert len(data) < 5 * 1024 * 1024, (
        "test precondition: the payload must fit the byte cap while still "
        "exceeding the dimension cap"
    )

    bounded = bound_artwork_dimensions(data)

    with Image.open(io.BytesIO(bounded)) as img:
        assert max(img.size) <= MAX_ARTWORK_DIMENSION


def test_shared_helper_leaves_small_images_untouched():
    data = _png_bytes(512, 512)
    assert bound_artwork_dimensions(data) == data


def test_downloader_save_artwork_bounds_dimensions(tmp_path):
    """WIRING: _save_artwork runs the bound helper (off the event loop)."""
    downloader = ArtworkDownloader(cache_dir=str(tmp_path))
    oversized = _png_bytes(8000, 8000)

    saved = asyncio.run(downloader._save_artwork(oversized, album_id=42, ext="jpg"))

    with Image.open(saved) as stored:
        assert max(stored.size) <= MAX_ARTWORK_DIMENSION


def test_downloader_save_artwork_keeps_small_bytes_verbatim(tmp_path):
    downloader = ArtworkDownloader(cache_dir=str(tmp_path))
    small = _png_bytes(300, 300)

    saved = asyncio.run(downloader._save_artwork(small, album_id=7, ext="jpg"))

    assert Path(saved).read_bytes() == small
