"""Unified backend cache invalidation contract (#5257)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "auralis-web" / "backend"))

from core import mastering_target_service
from core.cache_cleanup import clear_all_caches
from core.mastering_target_service import MasteringTargetService


@pytest.mark.asyncio
async def test_clear_all_caches_reaches_every_backend_cache(tmp_path, monkeypatch):
    artwork_dir = tmp_path / "artwork"
    thumb_dir = artwork_dir / "thumbnails"
    thumb_dir.mkdir(parents=True)
    (artwork_dir / "source.jpg").write_bytes(b"source")
    (thumb_dir / "thumbnail.png").write_bytes(b"thumb")
    cache_manager = AsyncMock()
    # #5085: the analysis tier is the live per-track fingerprint/target cache.
    service = MasteringTargetService()
    monkeypatch.setattr(mastering_target_service, "_global_mastering_target_service", service)
    service.cache["fingerprint_1_abcd1234"] = (object(), {"target_lufs": -14.0})

    result = await clear_all_caches(
        cache_manager,
        artwork_dir,
        clear_source_artwork=True,
        # #5340: the chunk sweep defaults to the real shared cache directory.
        chunk_dir=tmp_path / "chunks",
    )

    cache_manager.clear_all.assert_awaited_once_with()
    assert result.artwork_files_removed == 2
    assert result.artwork_bytes_reclaimed == 11
    assert result.analysis_cache_cleared is True
    assert len(service.cache) == 0
    assert list(artwork_dir.rglob("*")) == []


@pytest.mark.asyncio
async def test_clear_reports_no_analysis_tier_when_service_never_created(tmp_path, monkeypatch):
    """Clearing must not build the singleton just to report on it (#5085)."""
    monkeypatch.setattr(mastering_target_service, "_global_mastering_target_service", None)

    result = await clear_all_caches(None, tmp_path / "artwork", chunk_dir=tmp_path / "chunks")

    assert result.analysis_cache_cleared is False
    assert mastering_target_service._global_mastering_target_service is None


@pytest.mark.asyncio
async def test_standard_clear_preserves_database_backed_source_artwork(tmp_path):
    artwork_dir = tmp_path / "artwork"
    thumb_dir = artwork_dir / "thumbnails"
    thumb_dir.mkdir(parents=True)
    source = artwork_dir / "source.jpg"
    source.write_bytes(b"source")
    (thumb_dir / "thumbnail.png").write_bytes(b"thumb")

    result = await clear_all_caches(None, artwork_dir, chunk_dir=tmp_path / "chunks")

    assert result.artwork_files_removed == 1
    assert source.read_bytes() == b"source"
    assert list(thumb_dir.iterdir()) == []
