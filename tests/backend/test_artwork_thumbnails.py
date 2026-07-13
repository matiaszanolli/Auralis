"""
Artwork thumbnail generation (#4447)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the downscaled-thumbnail helpers added to the artwork router so
small consumers (40x40 track rows, album grid cards) no longer force the
browser to decode/hold full-resolution bitmaps.

Covers: size bucketing, format mapping, real Pillow resize + on-disk caching,
never-upscale behaviour, and graceful failure on a non-image source.
"""

from pathlib import Path

import pytest

from routers.artwork import (
    _bucket_size,
    _thumb_target,
    _get_or_create_thumbnail,
    _THUMB_BUCKETS,
)

PIL_Image = pytest.importorskip("PIL.Image")


def _make_source_image(path: Path, width: int, height: int, fmt: str = "PNG") -> Path:
    img = PIL_Image.new("RGB", (width, height), color=(120, 60, 200))
    img.save(path, format=fmt)
    return path


class TestBucketing:
    def test_snaps_up_to_nearest_bucket(self):
        assert _bucket_size(40) == 64
        assert _bucket_size(64) == 64
        assert _bucket_size(80) == 128
        assert _bucket_size(256) == 256

    def test_clamps_oversized_requests_to_the_largest_bucket(self):
        assert _bucket_size(99999) == _THUMB_BUCKETS[-1]


class TestThumbTarget:
    def test_jpeg_and_webp_preserved_others_png(self):
        assert _thumb_target("image/jpeg") == ("JPEG", ".jpg", "image/jpeg")
        assert _thumb_target("image/webp") == ("WEBP", ".webp", "image/webp")
        # PNG/GIF/unknown → PNG so transparency survives.
        assert _thumb_target("image/gif") == ("PNG", ".png", "image/png")
        assert _thumb_target("image/png") == ("PNG", ".png", "image/png")


class TestGetOrCreateThumbnail:
    def test_generates_a_downscaled_variant_and_caches_it(self, tmp_path):
        src = _make_source_image(tmp_path / "art.png", 1000, 800)
        thumb_dir = tmp_path / "thumbnails"

        result = _get_or_create_thumbnail(src, 128, "image/png", thumb_dir)
        assert result is not None
        path, media_type = result

        assert path.exists()
        assert path.parent == thumb_dir
        assert media_type == "image/png"

        # Downscaled: longest side == the 128 bucket, aspect ratio preserved.
        with PIL_Image.open(path) as im:
            assert max(im.size) == 128
            assert im.size == (128, 102)  # 1000x800 → 128x102 (rounded)

        # Second call is a cache hit — same path, no regeneration needed.
        again = _get_or_create_thumbnail(src, 128, "image/png", thumb_dir)
        assert again is not None
        assert again[0] == path

    def test_never_upscales_a_small_source(self, tmp_path):
        src = _make_source_image(tmp_path / "tiny.png", 48, 48)
        thumb_dir = tmp_path / "thumbnails"

        result = _get_or_create_thumbnail(src, 512, "image/png", thumb_dir)
        assert result is not None
        with PIL_Image.open(result[0]) as im:
            assert im.size == (48, 48)  # unchanged — thumbnail() only downsizes

    def test_jpeg_source_written_as_jpeg(self, tmp_path):
        src = _make_source_image(tmp_path / "photo.jpg", 600, 600, fmt="JPEG")
        thumb_dir = tmp_path / "thumbnails"

        result = _get_or_create_thumbnail(src, 256, "image/jpeg", thumb_dir)
        assert result is not None
        path, media_type = result
        assert path.suffix == ".jpg"
        assert media_type == "image/jpeg"

    def test_returns_none_on_a_non_image_source(self, tmp_path):
        bad = tmp_path / "not_an_image.png"
        bad.write_bytes(b"this is definitely not a PNG")
        thumb_dir = tmp_path / "thumbnails"

        # Falls back to None so the caller serves the original instead of 500ing.
        assert _get_or_create_thumbnail(bad, 128, "image/png", thumb_dir) is None

    def test_source_edit_invalidates_the_cache_key(self, tmp_path):
        src = _make_source_image(tmp_path / "art.png", 400, 400)
        thumb_dir = tmp_path / "thumbnails"

        first = _get_or_create_thumbnail(src, 128, "image/png", thumb_dir)
        # Re-write the source with different content/size → new mtime + size.
        _make_source_image(src, 640, 480)
        second = _get_or_create_thumbnail(src, 128, "image/png", thumb_dir)

        assert first is not None and second is not None
        # Different cache key (mtime/size embedded) → different file.
        assert first[0] != second[0]
