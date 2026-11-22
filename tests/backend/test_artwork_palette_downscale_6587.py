"""Palette (indexed PNG / GIF) covers are downscaled with filtering, not nearest-neighbour (#6587).

Pillow forces NEAREST resampling for mode ``P`` and ``1``, and both downscale paths (the thumbnail
route and the >2048 px bound on write) shrank the image in its native mode, so an indexed cover
came out as jagged, aliased pixels.
"""

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from PIL import Image

from routers.artwork_thumbnails import _render_thumbnail  # noqa: E402

from auralis.utils import artwork_security  # noqa: E402
from auralis.utils.artwork_security import bound_artwork_dimensions, downscaled  # noqa: E402


def _checkerboard(size: int, mode: str):
    """One-pixel black/white checkerboard: any filtering averages it to mid-grey (~128)."""
    grey = Image.new("L", (size, size))
    grey.putdata([255 * ((x + y) % 2) for y in range(size) for x in range(size)])
    return grey.convert(mode)


def _mean(image) -> float:
    lum = image.convert("L")
    return sum(lum.getdata()) / (lum.width * lum.height)


def _png(image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("mode", ["P", "1"])
def test_a_palette_or_bilevel_checkerboard_averages_like_the_rgb_source(mode):
    reference = _mean(downscaled(_checkerboard(512, "RGB"), 64))

    assert reference == pytest.approx(127.5, abs=2)
    assert _mean(downscaled(_checkerboard(512, mode), 64)) == pytest.approx(reference, abs=2)


def test_the_thumbnail_route_filters_a_palette_png(tmp_path):
    src = tmp_path / "cover.png"
    src.write_bytes(_png(_checkerboard(512, "P")))
    dst = tmp_path / "thumb.png"

    _render_thumbnail(src, dst, 64, "PNG", ".png", tmp_path)

    thumb = Image.open(dst)
    assert thumb.size == (64, 64)
    assert _mean(thumb) == pytest.approx(127.5, abs=2)


def test_a_transparent_palette_index_keeps_its_alpha(tmp_path):
    image = Image.new("P", (400, 400), 0)
    image.putpalette([255, 0, 0] + [0, 0, 255] * 255)
    image.paste(1, (200, 0, 400, 400))  # right half opaque blue, left half index 0 (transparent)
    image.info["transparency"] = 0
    src = tmp_path / "cover.png"
    image.save(src, format="PNG", transparency=0)
    dst = tmp_path / "thumb.png"

    _render_thumbnail(src, dst, 100, "PNG", ".png", tmp_path)

    thumb = Image.open(dst).convert("RGBA")
    assert thumb.getpixel((10, 50))[3] == 0
    assert thumb.getpixel((90, 50)) == (0, 0, 255, 255)


def test_the_write_path_bound_filters_a_palette_gif_and_keeps_its_format(monkeypatch):
    monkeypatch.setattr(artwork_security, "MAX_ARTWORK_DIMENSION", 64)
    buf = io.BytesIO()
    _checkerboard(512, "P").save(buf, format="GIF")

    result = bound_artwork_dimensions(buf.getvalue())

    assert result is not None
    out = Image.open(io.BytesIO(result))
    assert out.format == "GIF"
    assert out.size == (64, 64)
    assert _mean(out) == pytest.approx(127.5, abs=8)  # GIF re-quantises the grey
