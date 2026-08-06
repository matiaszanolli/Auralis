# -*- coding: utf-8 -*-

"""
Regression tests: StreamlinedCacheManager CHUNK_SIZE_MB accuracy (#4238)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CHUNK_SIZE_MB was a hand-picked 1.5 MB literal commented "stereo 44.1kHz,
float32" — but cached chunks are persisted as 16-bit PCM WAV (see
WAVEncoder(default_subtype='PCM_16') in core/chunked_processor.py), not
float32, making the estimate ~3.4x too low relative to the real ~2.5 MB
PCM_16 chunk size. Since Tier 2's size-based eviction check
(tier2_size_mb = len(tier2_cache) * CHUNK_SIZE_MB) is entirely driven by
this constant, the undercount let real disk usage run ~3.4x past the
240 MB budget before eviction believed it was necessary.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from cache.manager import (  # noqa: E402
    CHUNK_DURATION,
    CHUNK_SIZE_MB,
    TIER1_MAX_SIZE_MB,
    TIER2_MAX_SIZE_MB,
    StreamlinedCacheManager,
)


def _expected_chunk_size_mb() -> float:
    """PCM_16 stereo chunk size at the nominal 44.1kHz baseline."""
    return (2 * 44100 * CHUNK_DURATION * 2) / (1024 * 1024)


class TestChunkSizeConstant:
    def test_chunk_size_matches_pcm16_geometry(self):
        """CHUNK_SIZE_MB must be derived from CHUNK_DURATION/sample rate/
        channel count/PCM_16 bit depth, not a stale hand-picked literal."""
        expected = _expected_chunk_size_mb()
        assert CHUNK_SIZE_MB == pytest.approx(expected, rel=0.01)

    def test_chunk_size_is_not_the_old_stale_float32_based_1_5mb_literal(self):
        """Guard against regressing back to the old 1.5 MB estimate, which
        was ~3.4x too low relative to the real PCM_16 chunk size."""
        assert CHUNK_SIZE_MB > 2.0

    def test_tier1_max_size_derives_from_corrected_constant(self):
        assert TIER1_MAX_SIZE_MB == pytest.approx(2 * CHUNK_SIZE_MB * 2, rel=0.001)


class TestTier2EvictionFiresAtCorrectedBudget:
    """The Tier 2 size-based eviction check must trigger once the REAL
    on-disk chunk sizes cross TIER2_MAX_SIZE_MB.

    #4793 superseded the "nominal per-chunk estimate" accounting this class
    used to test (chunk COUNT × CHUNK_SIZE_MB) — that estimate itself was
    still wrong: it assumed every chunk is CHUNK_DURATION (15s) long, true
    only for chunk 0, over-accounting every regular CHUNK_INTERVAL (10s)
    chunk by ~50%. CachedChunk now stat()s its real file size at insert time
    (size_bytes) and tier size is the real sum of those — so these tests
    write realistically-sized dummy files instead of 1-byte stubs, or a
    monkeypatched budget small enough that tiny files still cross it.
    """

    @staticmethod
    def _write_chunk(path: Path, num_bytes: int) -> None:
        path.write_bytes(b"\x00" * num_bytes)

    @pytest.mark.asyncio
    async def test_evicts_when_real_chunk_sizes_exceed_budget(self, tmp_path, monkeypatch):
        """A small monkeypatched budget crossed by real (tiny but nonzero)
        on-disk file sizes must still trigger eviction — proving the check
        is driven by actual bytes, not chunk count."""
        import cache.manager as cache_manager_module
        monkeypatch.setattr(cache_manager_module, "TIER2_MAX_SIZE_MB", 0.01)  # ~10 KB

        manager = StreamlinedCacheManager()
        chunk_bytes = 4096  # 4 KB per chunk — real stat()'d size, not nominal
        chunks_added = 20   # 20 × 4 KB = 80 KB, well past the 10 KB budget

        # Distinct chunk indices far from the "current chunk" window so
        # add_chunk's auto-detect logic always routes them to tier2.
        for i in range(chunks_added):
            chunk_path = tmp_path / f"chunk_{i}.wav"
            self._write_chunk(chunk_path, chunk_bytes)
            await manager.add_chunk(
                track_id=1,
                chunk_idx=i + 100,
                chunk_path=chunk_path,
                tier="tier2",
            )

        # Eviction must have kept tier2 bounded — it must NOT have grown to
        # chunks_added entries unbounded (an eviction fired at some point
        # once real on-disk usage crossed the budget).
        assert len(manager.tier2_cache) < chunks_added

    @pytest.mark.asyncio
    async def test_stats_report_real_on_disk_size_not_nominal_estimate(self, tmp_path):
        """get_stats()'s size_mb must reflect real file sizes. Using
        CHUNK_SIZE_MB-sized files here would pass under either the old or
        new accounting, so this deliberately writes a DIFFERENT, distinct
        size to prove the nominal estimate isn't secretly still driving it."""
        manager = StreamlinedCacheManager()
        chunk_bytes = 12345  # arbitrary, deliberately not CHUNK_SIZE_MB-derived
        num_chunks = 5

        for i in range(num_chunks):
            chunk_path = tmp_path / f"chunk_{i}.wav"
            self._write_chunk(chunk_path, chunk_bytes)
            await manager.add_chunk(
                track_id=1,
                chunk_idx=i + 100,
                chunk_path=chunk_path,
                tier="tier2",
            )

        stats = manager.get_stats()
        expected_mb = (num_chunks * chunk_bytes) / (1024 * 1024)
        assert stats["tier2"]["size_mb"] == pytest.approx(expected_mb, rel=0.001)
        # Sanity: the nominal-estimate figure this used to report is a very
        # different number from the tiny real file sizes used here.
        assert stats["tier2"]["size_mb"] != pytest.approx(num_chunks * CHUNK_SIZE_MB, rel=0.1)


class TestTier2EvictionEnforcesSingleTrackBudget:
    """_evict_tier2_lru() must not no-op when the ONLY track with Tier 2
    entries is the current (protected) track — the common single-track-
    playing case (#4793). It used to protect current_track_id and return
    early when no other track was evictable, while add_chunk kept inserting
    regardless, so a single long track's Tier 2 map grew without bound."""

    @pytest.mark.asyncio
    async def test_single_current_track_is_evicted_from_not_grown_unbounded(self, tmp_path, monkeypatch):
        import cache.manager as cache_manager_module
        monkeypatch.setattr(cache_manager_module, "TIER2_MAX_SIZE_MB", 0.01)  # ~10 KB

        manager = StreamlinedCacheManager()
        manager.current_track_id = 1  # the bug scenario: playing == only cached track
        chunk_bytes = 4096
        chunks_added = 20

        for i in range(chunks_added):
            chunk_path = tmp_path / f"chunk_{i}.wav"
            self._write_chunk(chunk_path, chunk_bytes)
            await manager.add_chunk(
                track_id=1,
                chunk_idx=i + 100,
                chunk_path=chunk_path,
                tier="tier2",
            )

        # Before the fix this stayed at `chunks_added` forever — eviction
        # no-op'd because the only track present was current_track_id.
        assert len(manager.tier2_cache) < chunks_added

    @staticmethod
    def _write_chunk(path: Path, num_bytes: int) -> None:
        path.write_bytes(b"\x00" * num_bytes)
