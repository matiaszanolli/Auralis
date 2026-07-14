"""Regression tests for downloaded-artwork extension detection (#4419).

_try_musicbrainz/_try_itunes call _save_artwork with a hardcoded "jpg", but
Cover Art Archive / iTunes can return PNG/WebP. The GET endpoint infers
Content-Type from the extension, so a PNG saved .jpg is served image/jpeg.
_save_artwork now sniffs the real format from magic bytes.
"""

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.artwork_downloader import (  # noqa: E402
    ArtworkDownloader,
    _detect_image_extension,
)

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
_WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 8
_GIF = b"GIF89a" + b"\x00" * 16


@pytest.mark.parametrize(
    "data,expected",
    [
        (_PNG, "png"),
        (_JPEG, "jpg"),
        (_WEBP, "webp"),
        (_GIF, "gif"),
        (b"not-an-image", "jpg"),  # fallback to default
    ],
)
def test_detect_image_extension(data, expected):
    assert _detect_image_extension(data, default="jpg") == expected


@pytest.mark.asyncio
async def test_save_artwork_uses_detected_extension(tmp_path):
    downloader = ArtworkDownloader(cache_dir=str(tmp_path))

    png_path = await downloader._save_artwork(_PNG, album_id=1, ext="jpg")
    assert png_path.endswith(".png")
    assert Path(png_path).exists()

    webp_path = await downloader._save_artwork(_WEBP, album_id=2, ext="jpg")
    assert webp_path.endswith(".webp")


@pytest.mark.asyncio
async def test_save_artwork_falls_back_to_default_for_unknown_bytes(tmp_path):
    downloader = ArtworkDownloader(cache_dir=str(tmp_path))
    path = await downloader._save_artwork(b"garbage-bytes", album_id=3, ext="jpg")
    assert path.endswith(".jpg")
