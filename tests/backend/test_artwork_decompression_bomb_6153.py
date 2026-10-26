"""
Decompression-bomb artwork is rejected, not stored or served (#6153)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``bound_artwork_dimensions`` wrapped ``Image.open`` in ``except Exception:
return data``, so the one image it exists to stop (Pillow raises
``DecompressionBombError`` above ~179 Mpx) was stored and later served unchanged,
and the thumbnail route fell back to the original after the same error.

Pillow decides from the IHDR alone, so these fixtures are a PNG header plus a
token IDAT: tiny on disk, absurd on paper, never decoded.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import struct
import sys
import zlib
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.artwork import ArtworkExtractor  # noqa: E402
from auralis.utils.artwork_security import (  # noqa: E402
    MAX_LOCAL_ARTWORK_BYTES,
    bound_artwork_dimensions,
)
from fastapi import HTTPException  # noqa: E402
from routers import artwork_thumbnails  # noqa: E402


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def _png_claiming(width: int, height: int) -> bytes:
    """A 1-bit greyscale PNG whose header claims ``width`` x ``height``."""
    ihdr = struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(b"\x00"))
        + _chunk(b"IEND", b"")
    )


# 100000 x 100000 trips Pillow's own DecompressionBombError; 12000 x 12000
# (144 Mpx) is in its warn-only band and only the artwork pixel budget stops it.
_BOMBS = {"pillow-error": (100_000, 100_000), "warn-band": (12_000, 12_000)}


@pytest.mark.parametrize("size", _BOMBS.values(), ids=_BOMBS.keys())
def test_bound_artwork_dimensions_rejects_a_bomb(size):
    assert bound_artwork_dimensions(_png_claiming(*size)) is None


def test_unparseable_bytes_still_pass_through():
    """Only bombs are dropped; an unreadable file keeps the best-effort contract."""
    junk = b"not an image at all"

    assert bound_artwork_dimensions(junk) == junk


@pytest.mark.parametrize("size", _BOMBS.values(), ids=_BOMBS.keys())
def test_extractor_stores_no_artwork_for_a_bomb(tmp_path, size):
    extractor = ArtworkExtractor(str(tmp_path))

    assert extractor._save_artwork(_png_claiming(*size), album_id=1, mime_type="image/png") is None
    assert list(tmp_path.iterdir()) == []


def test_extractor_skips_pictures_over_the_byte_cap_without_decoding(tmp_path):
    extractor = ArtworkExtractor(str(tmp_path))
    oversized = b"\0" * (MAX_LOCAL_ARTWORK_BYTES + 1)

    with patch("auralis.library.artwork.bound_artwork_dimensions") as bound:
        assert extractor._save_artwork(oversized, album_id=1, mime_type="image/jpeg") is None

    bound.assert_not_called()


def test_a_rejected_embedded_cover_falls_back_to_folder_art(tmp_path):
    from PIL import Image

    folder = tmp_path / "album"
    folder.mkdir()
    (folder / "track.mp3").write_bytes(b"x")
    Image.new("RGB", (64, 64), (1, 2, 3)).save(folder / "cover.jpg", format="JPEG")
    extractor = ArtworkExtractor(str(tmp_path / "artwork"))

    with patch("auralis.library.artwork.MutagenFile"), \
         patch.object(extractor, "_extract_from_generic", return_value=(_png_claiming(100_000, 100_000), "image/png")):
        saved = extractor.extract_artwork(str(folder / "track.mp3"), album_id=7)

    assert saved is not None
    assert Path(saved).exists()
    assert Image.open(saved).size == (64, 64)


def test_thumbnail_of_a_bomb_is_a_404_never_the_original(tmp_path):
    source = tmp_path / "bomb.png"
    source.write_bytes(_png_claiming(100_000, 100_000))

    with pytest.raises(HTTPException) as caught:
        artwork_thumbnails._get_or_create_thumbnail(source, 256, "image/png", tmp_path / "thumbs")

    assert caught.value.status_code == 404
    assert list((tmp_path / "thumbs").iterdir()) == []


def test_thumbnail_of_an_ordinary_cover_still_renders(tmp_path):
    from PIL import Image

    source = tmp_path / "cover.png"
    Image.new("RGB", (900, 900), (9, 9, 9)).save(source, format="PNG")

    result = artwork_thumbnails._get_or_create_thumbnail(source, 256, "image/png", tmp_path / "thumbs")

    assert result is not None
    assert max(Image.open(result[0]).size) <= 256
