"""Re-encoded artwork keeps its EXIF orientation (baked in) and ICC profile (#5927).

Image.save() was called without exif= / icc_profile=, so a camera JPEG with orientation 6 came
out of the thumbnail renderer sideways relative to the original the browser rotates, and a
wide-gamut cover lost its profile.
"""

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

Image = pytest.importorskip("PIL.Image")

from routers.artwork_thumbnails import _render_thumbnail  # noqa: E402

from auralis.utils import artwork_security  # noqa: E402
from auralis.utils.artwork_security import bound_artwork_dimensions, upright_with_profile  # noqa: E402

# A minimal but valid ICC profile header is enough for Pillow to round-trip the bytes.
ICC = b"\x00\x00\x02\x0c" + b"lcms" + b"\x02\x10\x00\x00mntrRGB XYZ " + b"\x00" * 100


def _landscape_jpeg(width=400, height=200, orientation=6, icc=None):
    """Left half red, right half blue; EXIF says it must be rotated 90° clockwise to display."""
    image = Image.new("RGB", (width, height), "red")
    image.paste("blue", (width // 2, 0, width, height))
    exif = Image.Exif()
    exif[0x0112] = orientation
    buf = io.BytesIO()
    kwargs = {"icc_profile": icc} if icc else {}
    image.save(buf, format="JPEG", exif=exif, **kwargs)
    return buf.getvalue()


def _render(tmp_path, data, bucket=100):
    src = tmp_path / "cover.jpg"
    src.write_bytes(data)
    dst = tmp_path / "thumb.jpg"
    _render_thumbnail(src, dst, bucket, "JPEG", ".jpg", tmp_path)
    return Image.open(dst)


def test_thumbnail_of_an_oriented_jpeg_is_rotated_upright(tmp_path):
    thumb = _render(tmp_path, _landscape_jpeg())

    # Orientation 6 turns a 400x200 landscape into a portrait; red-left becomes red-top.
    assert thumb.height > thumb.width
    assert thumb.getexif().get(0x0112) in (None, 1)
    assert thumb.getpixel((thumb.width // 2, 2))[0] > 150      # top is red
    assert thumb.getpixel((thumb.width // 2, thumb.height - 3))[2] > 150  # bottom is blue


def test_thumbnail_keeps_the_icc_profile(tmp_path):
    thumb = _render(tmp_path, _landscape_jpeg(icc=ICC))

    assert thumb.info.get("icc_profile") == ICC


def test_an_unoriented_jpeg_is_unchanged_in_shape(tmp_path):
    thumb = _render(tmp_path, _landscape_jpeg(orientation=1))

    assert thumb.width > thumb.height


def test_oversized_artwork_downscale_keeps_orientation_and_profile(monkeypatch):
    monkeypatch.setattr(artwork_security, "MAX_ARTWORK_DIMENSION", 100)

    out = Image.open(io.BytesIO(bound_artwork_dimensions(_landscape_jpeg(icc=ICC))))

    assert out.height > out.width
    assert out.info.get("icc_profile") == ICC


def test_a_cmyk_profile_is_not_carried_to_the_rgb_copy():
    image = Image.new("CMYK", (4, 4))
    image.info["icc_profile"] = ICC

    _, kwargs = upright_with_profile(image)

    assert kwargs == {}
