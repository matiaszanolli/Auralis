"""Chunk-cache keys quantise intensity at one shared precision (#5474).

Every chunk-cache tier used to format the continuous intensity at its own
precision when building keys: the in-memory SimpleChunkCache tier at ``.1f``,
the on-disk key and WAV filename on the raw float. Two requests in the same
0.1 bucket (0.06 vs 0.14) therefore shared the in-memory entry but got
distinct on-disk entries, and float noise (0.30000000000000004) minted its
own unreachable disk files. All key builders now go through the canonical
``intensity_cache_key`` and must agree — including cross-tier, and including
``clear_track_cache``'s preset+intensity prefix.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from core.chunk_cache_manager import (  # noqa: E402
    ChunkCacheManager,
    intensity_cache_key,
)
from core.encoding.wav_encoder import WAVEncoder  # noqa: E402
from core.streamlined_processor_cache import intensity_key  # noqa: E402
from core.targets_hash import NO_TARGETS, get_targets_hash  # noqa: E402
from cache.models import CachedChunk  # noqa: E402

OFF_GRID_A = 0.06
OFF_GRID_B = 0.14
FLOAT_NOISE = 0.1 + 0.2  # 0.30000000000000004


class TestCrossTierIntensityPrecision:
    def test_on_disk_key_buckets_off_grid_intensities_together(self):
        a = ChunkCacheManager.get_chunk_cache_key(1, "sig", "adaptive", OFF_GRID_A, 0)
        b = ChunkCacheManager.get_chunk_cache_key(1, "sig", "adaptive", OFF_GRID_B, 0)
        assert a == b

    def test_on_disk_key_absorbs_float_noise(self):
        clean = ChunkCacheManager.get_chunk_cache_key(1, "sig", "adaptive", 0.3, 0)
        noisy = ChunkCacheManager.get_chunk_cache_key(1, "sig", "adaptive", FLOAT_NOISE, 0)
        assert clean == noisy

    def test_wav_filename_buckets_off_grid_intensities_together(self, tmp_path):
        encoder = WAVEncoder(chunk_dir=tmp_path)
        a = encoder.get_chunk_path(1, "sig", "adaptive", OFF_GRID_A, 0, NO_TARGETS)
        b = encoder.get_chunk_path(1, "sig", "adaptive", OFF_GRID_B, 0, NO_TARGETS)
        assert a == b

    def test_simple_chunk_cache_key_buckets_off_grid_intensities_together(self):
        a = CachedChunk.make_key(1, 0, "adaptive", OFF_GRID_A, "sig")
        b = CachedChunk.make_key(1, 0, "adaptive", OFF_GRID_B, "sig")
        assert a == b

    def test_processor_bucketing_shares_the_canonical_formatter(self):
        assert intensity_key(OFF_GRID_A) == intensity_key(OFF_GRID_B)
        assert intensity_key(FLOAT_NOISE) == intensity_key(0.3)
        assert intensity_key(0.4951) == intensity_key(0.5049) == 0.5

    def test_intensity_segments_agree_across_tiers(self):
        """The intensity component of every key format is the same string."""
        disk_key = ChunkCacheManager.get_chunk_cache_key(
            1, "sig", "adaptive", OFF_GRID_A, 0, get_targets_hash(None)
        )
        memory_key = CachedChunk.make_key(1, 0, "adaptive", OFF_GRID_A, "sig")
        disk_segment = disk_key.split("_")[3]
        memory_segment = memory_key.split("_")[2]
        assert disk_segment == memory_segment == str(intensity_cache_key(OFF_GRID_A))


class TestClearTrackCachePrefixQuantised:
    def test_preset_intensity_prefix_matches_float_noise_entries(self):
        key = ChunkCacheManager.get_chunk_cache_key(123, "sig", "adaptive", FLOAT_NOISE, 0)
        manager = ChunkCacheManager({key: "/tmp/a.wav"})
        # The caller passes the same noisy float; the prefix must quantise it
        # the same way the key builder did or the entry survives the clear.
        assert manager.clear_track_cache(123, "sig", "adaptive", FLOAT_NOISE) == 1

    def test_preset_intensity_prefix_matches_off_grid_bucket(self):
        key = ChunkCacheManager.get_chunk_cache_key(123, "sig", "adaptive", OFF_GRID_B, 0)
        manager = ChunkCacheManager({key: "/tmp/a.wav"})
        assert manager.clear_track_cache(123, "sig", "adaptive", OFF_GRID_B) == 1


class TestOnGridIntensitiesUnchanged:
    def test_grid_values_format_unchanged(self):
        """Pre-fix on-grid behaviour is preserved — no mass invalidation."""
        for value in (0.0, 0.1, 0.5, 0.8, 1.0):
            assert ChunkCacheManager.get_chunk_cache_key(
                123, "a3b4c5d6", "adaptive", value, 0
            ) == ChunkCacheManager.get_chunk_cache_key(
                123, "a3b4c5d6", "adaptive", value, 0, NO_TARGETS
            )
            assert str(intensity_cache_key(value)) == str(value)
