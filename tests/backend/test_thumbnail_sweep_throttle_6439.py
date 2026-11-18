"""A thumbnail cache miss no longer walks the whole cache directory twice (#6439).

``_get_or_create_thumbnail`` ran ``reap_orphan_temp_files`` (a glob) and
``prune_thumbnail_cache`` (iterdir + stat + sort) around every render, so first-loading a grid of
covers cost O(albums x cached files). The sweep now runs once per N renders and once at startup.
"""
import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from config.startup.thumbnail_store import sweep_thumbnail_store  # noqa: E402
from core.chunk_cache_manager import ChunkCacheManager  # noqa: E402
from core.thumbnail_cache import THUMB_TMP_PREFIX, prune_thumbnail_cache  # noqa: E402
from core.thumbnail_sweep import (  # noqa: E402
    THUMBNAIL_SWEEP_EVERY_N_RENDERS,
    ThumbnailSweeper,
    thumbnail_sweeper,
)
from routers.artwork_thumbnails import _get_or_create_thumbnail  # noqa: E402


@pytest.fixture
def thumb_dir(tmp_path) -> Path:
    d = tmp_path / "thumbnails"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _fresh_throttle():
    ThumbnailSweeper._write_counter = 0
    yield
    ThumbnailSweeper._write_counter = 0


def _png(path: Path) -> Path:
    from PIL import Image

    Image.new("RGB", (64, 64), (10, 120, 200)).save(path, format="PNG")
    return path


def test_renders_sweep_once_per_n_not_per_miss(thumb_dir, tmp_path):
    renders = 100
    sources = [_png(tmp_path / f"cover{i}.png") for i in range(renders)]

    with patch("core.thumbnail_sweep.prune_thumbnail_cache", wraps=prune_thumbnail_cache) as prune, \
            patch("core.thumbnail_sweep.reap_orphan_temp_files") as reap:
        for src in sources:
            assert _get_or_create_thumbnail(src, 256, "image/png", thumb_dir) is not None

    expected = renders // THUMBNAIL_SWEEP_EVERY_N_RENDERS
    assert prune.call_count == expected == 3
    assert reap.call_count == expected


def test_a_cache_hit_does_not_count_toward_the_sweep(thumb_dir, tmp_path):
    src = _png(tmp_path / "cover.png")
    assert _get_or_create_thumbnail(src, 256, "image/png", thumb_dir) is not None
    before = ThumbnailSweeper._write_counter

    for _ in range(50):
        _get_or_create_thumbnail(src, 256, "image/png", thumb_dir)

    assert ThumbnailSweeper._write_counter == before == 1


def test_the_cap_is_still_enforced_by_the_throttled_sweep(thumb_dir):
    files = []
    for i in range(6):
        f = thumb_dir / f"entry{i}.png"
        f.write_bytes(b"1234")
        os.utime(f, (1000 + i, 1000 + i))
        files.append(f)
    sweeper = ThumbnailSweeper(every=3, max_bytes=8)

    sweeper.note_render(thumb_dir)
    sweeper.note_render(thumb_dir)
    assert all(f.exists() for f in files), "no sweep before the N-th render"
    sweeper.note_render(thumb_dir)

    assert [f.exists() for f in files] == [False, False, False, False, True, True]


def test_orphaned_temp_files_are_reaped_by_the_sweep(thumb_dir):
    stale = thumb_dir / f"{THUMB_TMP_PREFIX}dead-writer"
    stale.write_bytes(b"x")
    old = time.time() - 3600
    os.utime(stale, (old, old))
    fresh = thumb_dir / f"{THUMB_TMP_PREFIX}live-writer"
    fresh.write_bytes(b"x")

    ThumbnailSweeper(every=1).note_render(thumb_dir)

    assert not stale.exists()
    assert fresh.exists()


def test_startup_sweep_reaps_orphans_and_runs_the_cap_enforcement(thumb_dir):
    stale = thumb_dir / f"{THUMB_TMP_PREFIX}dead-writer"
    stale.write_bytes(b"x")
    old = time.time() - 3600
    os.utime(stale, (old, old))
    with patch("config.startup.thumbnail_store.artwork_cache_dirs", return_value=(thumb_dir.parent, thumb_dir)), \
            patch("core.thumbnail_sweep.prune_thumbnail_cache", return_value=(2, 8)) as prune:
        deleted = asyncio.run(sweep_thumbnail_store())

    assert not stale.exists()
    assert prune.call_count == 1 and prune.call_args.args[0] == thumb_dir
    assert deleted == 2


def test_startup_sweep_failure_is_not_fatal():
    with patch("config.startup.thumbnail_store.artwork_cache_dirs", side_effect=RuntimeError("boom")):
        assert asyncio.run(sweep_thumbnail_store()) == 0


def test_thumbnail_throttle_is_independent_of_the_chunk_cache():
    assert ThumbnailSweeper._prune_lock is not ChunkCacheManager._prune_lock
    assert ThumbnailSweeper._prune_scan_lock is not ChunkCacheManager._prune_scan_lock
    chunk_before = ChunkCacheManager._write_counter
    thumbnail_sweeper.note_render(Path("/nonexistent-6439"))
    assert ChunkCacheManager._write_counter == chunk_before
