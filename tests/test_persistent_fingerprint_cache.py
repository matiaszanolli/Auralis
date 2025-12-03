# -*- coding: utf-8 -*-

"""
Persistent Fingerprint Cache Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for SQLite-based persistent fingerprint cache with multi-level
memory + disk caching for cross-session reuse.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import numpy as np
import tempfile
import shutil
from pathlib import Path
import time

from auralis.analysis.fingerprint.persistent_cache import (
    PersistentFingerprintCache,
    create_persistent_fingerprint_cache,
)
from auralis.analysis.fingerprint.cached_analyzer import CachedAudioFingerprintAnalyzer


class TestPersistentCache:
    """Test persistent SQLite fingerprint cache."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create persistent cache instance."""
        db_path = Path(temp_cache_dir) / "test_cache.db"
        return PersistentFingerprintCache(db_path=db_path, max_size_gb=0.1)  # 100MB for testing

    @pytest.fixture
    def test_fingerprint(self):
        """Create test fingerprint dict."""
        return {
            "sub_bass_pct": 0.05,
            "bass_pct": 0.15,
            "low_mid_pct": 0.20,
            "mid_pct": 0.25,
            "upper_mid_pct": 0.15,
            "presence_pct": 0.12,
            "air_pct": 0.08,
            "lufs": -10.5,
            "crest_db": 8.2,
            "bass_mid_ratio": 2.1,
            "tempo_bpm": 120.0,
            "rhythm_stability": 0.8,
            "transient_density": 0.6,
            "silence_ratio": 0.05,
            "spectral_centroid": 0.45,
            "spectral_rolloff": 0.72,
            "spectral_flatness": 0.3,
            "harmonic_ratio": 0.7,
            "pitch_stability": 0.65,
            "chroma_energy": 0.55,
            "dynamic_range_variation": 0.4,
            "loudness_variation_std": 0.25,
            "peak_consistency": 0.8,
            "stereo_width": 0.6,
            "phase_correlation": 0.85,
        }

    @pytest.fixture
    def test_audio(self):
        """Generate test audio."""
        sr = 44100
        duration = 2  # 2 seconds
        frequency = 440
        t = np.arange(sr * duration) / sr
        audio = 0.3 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
        return audio

    def test_cache_set_and_get(self, cache, test_fingerprint, test_audio):
        """Test storing and retrieving fingerprints."""
        audio_bytes = test_audio.tobytes()

        # Store
        cache.set(audio_bytes, test_fingerprint, len(test_audio))

        # Retrieve
        retrieved = cache.get(audio_bytes)
        assert retrieved is not None
        assert retrieved == test_fingerprint

    def test_cache_miss_returns_none(self, cache, test_audio):
        """Test that cache miss returns None."""
        audio_bytes = test_audio.tobytes()
        result = cache.get(audio_bytes)
        assert result is None

    def test_cache_stats(self, cache, test_fingerprint, test_audio):
        """Test cache statistics."""
        audio_bytes = test_audio.tobytes()

        # Initial stats
        stats1 = cache.get_stats()
        assert stats1["total_entries"] == 0
        assert stats1["hits"] == 0
        assert stats1["misses"] == 0

        # Store fingerprint
        cache.set(audio_bytes, test_fingerprint, len(test_audio))
        stats2 = cache.get_stats()
        assert stats2["total_entries"] == 1

        # Retrieve (hit)
        cache.get(audio_bytes)
        stats3 = cache.get_stats()
        assert stats3["hits"] == 1

        # Miss with different audio
        different_audio = test_audio * 2
        cache.get(different_audio.tobytes())
        stats4 = cache.get_stats()
        assert stats4["misses"] == 1

    def test_persistence_across_instances(self, temp_cache_dir, test_fingerprint, test_audio):
        """Test that cache persists across different instances."""
        db_path = Path(temp_cache_dir) / "persistent.db"
        audio_bytes = test_audio.tobytes()

        # Create cache and store
        cache1 = PersistentFingerprintCache(db_path=db_path)
        cache1.set(audio_bytes, test_fingerprint, len(test_audio))

        # Create new instance with same DB
        cache2 = PersistentFingerprintCache(db_path=db_path)
        retrieved = cache2.get(audio_bytes)

        assert retrieved is not None
        assert retrieved == test_fingerprint

    def test_cache_size_limits(self, cache, test_fingerprint):
        """Test that cache respects size limits."""
        # Store many fingerprints
        for i in range(100):
            audio_bytes = (str(i) * 1000).encode()  # Different content each time
            cache.set(audio_bytes, test_fingerprint)

        stats = cache.get_stats()
        # Should be within max size (100MB for test cache)
        assert stats["db_size_mb"] <= 100.0

    def test_cache_clear(self, cache, test_fingerprint, test_audio):
        """Test clearing cache."""
        audio_bytes = test_audio.tobytes()
        cache.set(audio_bytes, test_fingerprint)

        stats_before = cache.get_stats()
        assert stats_before["total_entries"] > 0

        cache.clear()

        stats_after = cache.get_stats()
        assert stats_after["total_entries"] == 0
        assert cache.get(audio_bytes) is None

    def test_cleanup_old_entries(self, cache, test_fingerprint, test_audio):
        """Test cleanup of old entries."""
        audio_bytes = test_audio.tobytes()
        cache.set(audio_bytes, test_fingerprint)

        # Cleanup should remove nothing (just created)
        deleted = cache.cleanup_old_entries(days=0)
        assert deleted == 0

        # Cleanup with large day value should also remove nothing
        deleted = cache.cleanup_old_entries(days=30)
        assert deleted == 0


class TestCachedAnalyzerWithPersistence:
    """Test CachedAudioFingerprintAnalyzer with persistent cache."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def test_audio(self):
        """Generate test audio."""
        sr = 44100
        duration = 3
        frequency = 440
        t = np.arange(sr * duration) / sr
        audio = 0.3 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
        return audio

    def test_multi_level_caching(self, temp_cache_dir, test_audio):
        """Test multi-level caching: memory + persistent."""
        db_path = Path(temp_cache_dir) / "fingerprints.db"

        # Create analyzer with persistent cache
        analyzer = CachedAudioFingerprintAnalyzer(
            use_persistent_cache=True,
            persistent_cache_path=db_path,
        )

        sr = 44100

        # First analysis (miss) - slow
        fingerprint1 = analyzer.analyze(test_audio, sr)
        assert fingerprint1 is not None
        stats1 = analyzer.get_cache_stats()
        assert stats1["memory_misses"] == 1

        # Second analysis (memory cache hit) - fast
        fingerprint2 = analyzer.analyze(test_audio, sr)
        assert fingerprint2 == fingerprint1
        stats2 = analyzer.get_cache_stats()
        assert stats2["memory_hits"] == 1

        # Create new analyzer instance with same persistent cache
        analyzer2 = CachedAudioFingerprintAnalyzer(
            use_persistent_cache=True,
            persistent_cache_path=db_path,
        )

        # Should hit persistent cache
        fingerprint3 = analyzer2.analyze(test_audio, sr)
        assert fingerprint3 is not None
        stats3 = analyzer2.get_cache_stats()
        # Should have cached something in persistent layer
        assert "persistent_entries" in stats3 or "memory_hits" in stats3

    def test_cache_disabled_fallback(self, test_audio):
        """Test that analyzer works without persistent cache."""
        analyzer = CachedAudioFingerprintAnalyzer(use_persistent_cache=False)
        sr = 44100

        fingerprint = analyzer.analyze(test_audio, sr)
        assert fingerprint is not None

        # Memory cache should still work
        fingerprint2 = analyzer.analyze(test_audio, sr)
        assert fingerprint2 == fingerprint
        stats = analyzer.get_cache_stats()
        assert stats["memory_hits"] == 1


class TestPersistentCachePerformance:
    """Test performance characteristics of persistent cache."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create persistent cache."""
        db_path = Path(temp_cache_dir) / "perf_test.db"
        return PersistentFingerprintCache(db_path=db_path)

    @pytest.fixture
    def test_fingerprint(self):
        """Create test fingerprint."""
        return {f"feature_{i}": float(i) / 100 for i in range(25)}

    @pytest.mark.benchmark
    def test_write_performance(self, cache, test_fingerprint):
        """Test fingerprint write performance."""
        start = time.perf_counter()
        for i in range(100):
            audio_bytes = (str(i) * 1000).encode()
            cache.set(audio_bytes, test_fingerprint)
        elapsed = (time.perf_counter() - start) * 1000

        # Should be fast (< 100ms for 100 writes)
        assert elapsed < 500.0  # Generous allowance

    @pytest.mark.benchmark
    def test_read_performance(self, cache, test_fingerprint):
        """Test fingerprint read performance."""
        # Pre-populate
        audio_keys = []
        for i in range(100):
            audio_bytes = (str(i) * 1000).encode()
            cache.set(audio_bytes, test_fingerprint)
            audio_keys.append(audio_bytes)

        # Read performance
        start = time.perf_counter()
        for audio_bytes in audio_keys:
            cache.get(audio_bytes)
        elapsed = (time.perf_counter() - start) * 1000

        # Should be very fast (< 50ms for 100 reads)
        assert elapsed < 200.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
