# -*- coding: utf-8 -*-

"""
Regression tests: StreamlinedCacheManager.get_stats() field placement (#4785)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

get_stats() used to put ``tracks_cached`` under ``tier2`` instead of
``overall``, disagreeing with schemas.OverallCacheStats, the TS
CacheStats/CacheStatsResponse types, and three Redux selectors, all of which
read it from ``overall.tracks_cached``. Each per-track entry in the
``tracks`` map also omitted ``track_id`` (the id was only the dict key),
while TrackCacheInfo/TrackCacheList require and render it directly.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from cache.manager import StreamlinedCacheManager  # noqa: E402
from schemas import OverallCacheStats  # noqa: E402


class TestTracksCachedUnderOverall:
    @pytest.mark.asyncio
    async def test_tracks_cached_is_under_overall_not_tier2(self, tmp_path):
        manager = StreamlinedCacheManager()

        for track_id in (1, 1, 2):
            chunk_path = tmp_path / f"chunk_{track_id}_{id(object())}.wav"
            chunk_path.write_bytes(b"\x00")
            await manager.add_chunk(
                track_id=track_id, chunk_idx=100, chunk_path=chunk_path, tier="tier2"
            )

        stats = manager.get_stats()

        assert "tracks_cached" not in stats["tier2"]
        assert stats["overall"]["tracks_cached"] == 2  # distinct track_ids

    @pytest.mark.asyncio
    async def test_overall_tracks_cached_validates_against_schema(self, tmp_path):
        """OverallCacheStats.tracks_cached is a required field — get_stats()'s
        "overall" dict must supply it directly, not rely on a caller default."""
        manager = StreamlinedCacheManager()
        chunk_path = tmp_path / "chunk.wav"
        chunk_path.write_bytes(b"\x00")
        await manager.add_chunk(
            track_id=1, chunk_idx=100, chunk_path=chunk_path, tier="tier2"
        )

        stats = manager.get_stats()

        # Raises pydantic.ValidationError if tracks_cached (or any other
        # required OverallCacheStats field) is missing from stats["overall"].
        validated = OverallCacheStats(**stats["overall"])
        assert validated.tracks_cached == 1


class TestTrackIdIncludedInTracksEntries:
    @pytest.mark.asyncio
    async def test_each_tracks_entry_includes_its_own_track_id(self):
        manager = StreamlinedCacheManager()
        await manager.update_position(
            track_id=42, position=0.0, preset="adaptive", intensity=1.0,
            track_duration=30.0,
        )

        stats = manager.get_stats()

        assert stats["tracks"][42]["track_id"] == 42
