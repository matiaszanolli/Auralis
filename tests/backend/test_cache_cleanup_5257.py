"""Unified backend cache invalidation contract (#5257)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "auralis-web" / "backend"))

from core.cache_cleanup import clear_all_caches  # noqa: E402
from analysis import track_analysis_cache  # noqa: E402


@pytest.mark.asyncio
async def test_clear_all_caches_reaches_every_backend_cache(tmp_path, monkeypatch):
    artwork_dir = tmp_path / "artwork"
    thumb_dir = artwork_dir / "thumbnails"
    thumb_dir.mkdir(parents=True)
    (artwork_dir / "source.jpg").write_bytes(b"source")
    (thumb_dir / "thumbnail.png").write_bytes(b"thumb")
    cache_manager = AsyncMock()
    monkeypatch.setattr(track_analysis_cache, "_track_analysis_cache", None)
    track_analysis_cache.init_track_analysis_cache()
    analysis_cache = track_analysis_cache.get_track_analysis_cache()
    analysis_cache.put(1, {"fingerprint": {"tempo": 120.0}})

    result = await clear_all_caches(
        cache_manager,
        artwork_dir,
        clear_source_artwork=True,
    )

    cache_manager.clear_all.assert_awaited_once_with()
    assert result.artwork_files_removed == 2
    assert result.artwork_bytes_reclaimed == 11
    assert result.analysis_cache_cleared is True
    assert analysis_cache.has(1) is False
    assert list(artwork_dir.rglob("*")) == []


@pytest.mark.asyncio
async def test_standard_clear_preserves_database_backed_source_artwork(tmp_path):
    artwork_dir = tmp_path / "artwork"
    thumb_dir = artwork_dir / "thumbnails"
    thumb_dir.mkdir(parents=True)
    source = artwork_dir / "source.jpg"
    source.write_bytes(b"source")
    (thumb_dir / "thumbnail.png").write_bytes(b"thumb")

    result = await clear_all_caches(None, artwork_dir)

    assert result.artwork_files_removed == 1
    assert source.read_bytes() == b"source"
    assert list(thumb_dir.iterdir()) == []
