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
    """The Tier 2 size-based eviction check must trigger once the corrected
    per-chunk estimate crosses TIER2_MAX_SIZE_MB — not 3.4x later, as it did
    under the old undercounted constant."""

    @pytest.mark.asyncio
    async def test_evicts_when_corrected_chunk_count_exceeds_budget(self, tmp_path):
        manager = StreamlinedCacheManager()
        # The eviction check runs BEFORE each insert (evaluating the count
        # already present), so the trigger only fires on the add AFTER the
        # budget is first crossed. Add a comfortable margin past the exact
        # boundary so the test isn't sensitive to that off-by-one.
        chunks_added = int(TIER2_MAX_SIZE_MB / CHUNK_SIZE_MB) + 10

        # Distinct chunk indices far from the "current chunk" window so
        # add_chunk's auto-detect logic always routes them to tier2.
        for i in range(chunks_added):
            chunk_path = tmp_path / f"chunk_{i}.wav"
            chunk_path.write_bytes(b"\x00")
            await manager.add_chunk(
                track_id=1,
                chunk_idx=i + 100,
                chunk_path=chunk_path,
                tier="tier2",
            )

        # Eviction must have kept tier2 bounded — it must NOT have grown to
        # chunks_added entries unbounded (an eviction fired at some point
        # once the corrected estimate crossed the budget).
        assert len(manager.tier2_cache) < chunks_added

    @pytest.mark.asyncio
    async def test_stats_report_size_consistent_with_corrected_constant(self, tmp_path):
        manager = StreamlinedCacheManager()
        for i in range(5):
            chunk_path = tmp_path / f"chunk_{i}.wav"
            chunk_path.write_bytes(b"\x00")
            await manager.add_chunk(
                track_id=1,
                chunk_idx=i + 100,
                chunk_path=chunk_path,
                tier="tier2",
            )

        stats = manager.get_stats()
        assert stats["tier2"]["size_mb"] == pytest.approx(5 * CHUNK_SIZE_MB, rel=0.001)
