# -*- coding: utf-8 -*-

"""
Phase 11 Optimization Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for fingerprint caching, lazy tempo detection, and preset parameters.

Validates:
1. Fingerprint caching with LRU eviction
2. Lazy tempo detection option
3. Pre-generated preset parameters

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import numpy as np
import time
from pathlib import Path

# Test imports
from auralis.analysis.fingerprint.cached_analyzer import CachedAudioFingerprintAnalyzer
from auralis.core.analysis.content_analyzer import ContentAnalyzer, create_content_analyzer
from auralis.core.processing.preset_parameters import PresetParameters, get_preset_parameters


class TestFingerprintCaching:
    """Test fingerprint caching with LRU eviction."""

    @pytest.fixture
    def cached_analyzer(self):
        """Create cached fingerprint analyzer with small cache for testing."""
        return CachedAudioFingerprintAnalyzer(max_cache_size=3)

    @pytest.fixture
    def test_audio(self):
        """Generate test audio."""
        sr = 44100
        duration = 5  # 5 seconds
        frequency = 440  # A4
        t = np.arange(sr * duration) / sr
        audio = 0.3 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
        return audio

    def test_cache_hit(self, cached_analyzer, test_audio):
        """Test cache hit returns cached result."""
        sr = 44100

        # First analysis (miss)
        result1 = cached_analyzer.analyze(test_audio, sr)
        assert isinstance(result1, dict)
        assert len(result1) > 0

        # Check stats
        stats1 = cached_analyzer.get_cache_stats()
        assert stats1["memory_misses"] == 1
        assert stats1["memory_hits"] == 0
        assert stats1["memory_cache_size"] == 1

        # Second analysis (hit)
        result2 = cached_analyzer.analyze(test_audio, sr)
        assert result2 == result1  # Same results

        # Check stats
        stats2 = cached_analyzer.get_cache_stats()
        assert stats2["memory_misses"] == 1
        assert stats2["memory_hits"] == 1
        assert stats2["memory_cache_size"] == 1

    def test_cache_lru_eviction(self, cached_analyzer, test_audio):
        """Test LRU eviction when cache is full."""
        sr = 44100

        # Generate 5 different audio samples
        for i in range(5):
            audio = test_audio + (i * 0.001)  # Slight variation
            cached_analyzer.analyze(audio, sr)

        # Cache should be evicted (max size 3)
        stats = cached_analyzer.get_cache_stats()
        assert stats["memory_cache_size"] <= 3

    def test_cache_stats(self, cached_analyzer, test_audio):
        """Test cache statistics reporting."""
        sr = 44100

        # Do some analyses
        cached_analyzer.analyze(test_audio, sr)
        cached_analyzer.analyze(test_audio, sr)  # Hit
        cached_analyzer.analyze(test_audio + 0.001, sr)  # Miss
        cached_analyzer.analyze(test_audio, sr)  # Hit

        stats = cached_analyzer.get_cache_stats()
        assert stats["memory_hits"] == 2
        assert stats["memory_misses"] == 2
        assert stats["memory_cache_size"] == 2
        assert stats["hit_rate_percent"] == 50.0

    def test_cache_clear(self, cached_analyzer, test_audio):
        """Test cache clearing."""
        sr = 44100

        cached_analyzer.analyze(test_audio, sr)
        stats_before = cached_analyzer.get_cache_stats()
        assert stats_before["memory_cache_size"] == 1

        cached_analyzer.clear_cache()
        stats_after = cached_analyzer.get_cache_stats()
        assert stats_after["memory_cache_size"] == 0


class TestLazyTempoDetection:
    """Test lazy tempo detection option."""

    @pytest.fixture
    def test_audio(self):
        """Generate test audio."""
        sr = 44100
        duration = 3  # 3 seconds
        frequency = 440  # A4
        t = np.arange(sr * duration) / sr
        audio = 0.3 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
        return audio

    def test_tempo_detection_enabled(self, test_audio):
        """Test that tempo detection works when enabled."""
        analyzer = ContentAnalyzer(use_tempo_detection=True)
        profile = analyzer.analyze_content(test_audio)

        assert "estimated_tempo" in profile
        assert 40 <= profile["estimated_tempo"] <= 300  # Valid BPM range

    def test_tempo_detection_disabled(self, test_audio):
        """Test that tempo detection is skipped when disabled."""
        analyzer = ContentAnalyzer(use_tempo_detection=False)
        profile = analyzer.analyze_content(test_audio)

        assert "estimated_tempo" in profile
        assert profile["estimated_tempo"] == 120.0  # Default when disabled

    def test_lazy_tempo_in_factory(self, test_audio):
        """Test lazy tempo detection in factory function."""
        analyzer_lazy = create_content_analyzer(use_tempo_detection=False)
        analyzer_eager = create_content_analyzer(use_tempo_detection=True)

        profile_lazy = analyzer_lazy.analyze_content(test_audio)
        profile_eager = analyzer_eager.analyze_content(test_audio)

        assert profile_lazy["estimated_tempo"] == 120.0
        assert profile_eager["estimated_tempo"] != 120.0  # Actual detection


class TestPresetParameters:
    """Test pre-generated mastering preset parameters."""

    def test_get_gentle_preset(self):
        """Test retrieving Gentle preset."""
        preset = PresetParameters.get_preset("gentle")

        assert preset["name"] == "Gentle"
        assert "eq_gains" in preset
        assert "dynamics" in preset
        assert "target_lufs" in preset
        assert isinstance(preset["eq_gains"], dict)
        assert isinstance(preset["dynamics"], dict)

    def test_get_all_presets(self):
        """Test retrieving all standard presets."""
        presets = ["gentle", "warm", "bright", "punchy"]

        for preset_name in presets:
            preset = PresetParameters.get_preset(preset_name)
            assert preset["name"].lower() == preset_name.lower()

    def test_preset_is_pregenerated(self):
        """Test checking if preset is pre-generated."""
        assert PresetParameters.is_preset_pregenerated("gentle")
        assert PresetParameters.is_preset_pregenerated("warm")
        assert not PresetParameters.is_preset_pregenerated("adaptive")

    def test_invalid_preset(self):
        """Test that invalid preset raises error."""
        with pytest.raises(ValueError):
            PresetParameters.get_preset("nonexistent")

    def test_preset_parameters_immutable(self):
        """Test that returned presets are copies (immutable)."""
        preset1 = PresetParameters.get_preset("gentle")
        preset1["modified"] = True

        preset2 = PresetParameters.get_preset("gentle")
        assert "modified" not in preset2

    def test_list_presets(self):
        """Test listing all available presets."""
        presets = PresetParameters.list_presets()

        assert len(presets) >= 4
        assert "gentle" in presets
        assert "warm" in presets
        assert "bright" in presets
        assert "punchy" in presets

    def test_convenience_function(self):
        """Test convenience function for getting preset parameters."""
        preset = get_preset_parameters("bright")
        assert preset["name"] == "Bright"

    def test_preset_eq_values(self):
        """Test that EQ values are within reasonable ranges."""
        for preset_name in ["gentle", "warm", "bright", "punchy"]:
            preset = PresetParameters.get_preset(preset_name)
            eq_gains = preset["eq_gains"]

            # EQ gains should be reasonable (typically -6dB to +6dB)
            for freq_band, gain in eq_gains.items():
                assert -6 <= gain <= 6, f"{preset_name} {freq_band}: {gain}"

    def test_preset_dynamics_values(self):
        """Test that dynamics parameters are within reasonable ranges."""
        for preset_name in ["gentle", "warm", "bright", "punchy"]:
            preset = PresetParameters.get_preset(preset_name)
            dynamics = preset["dynamics"]

            # Compressor ratio should be 1-8
            assert 1.0 <= dynamics["compressor_ratio"] <= 8.0
            # Threshold should be reasonable (-30dB to 0dB)
            assert -30 <= dynamics["compressor_threshold_db"] <= 0
            # Attack should be fast (1-100ms)
            assert 1 <= dynamics["compressor_attack_ms"] <= 100
            # Release should be reasonable (50-500ms)
            assert 50 <= dynamics["compressor_release_ms"] <= 500


class TestPerformanceImpact:
    """Test that optimizations provide expected performance benefits."""

    @pytest.mark.benchmark
    def test_fingerprint_cache_performance(self):
        """Test fingerprint cache performance improvement."""
        analyzer = CachedAudioFingerprintAnalyzer(max_cache_size=10)
        sr = 44100
        duration = 5
        t = np.arange(sr * duration) / sr
        audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

        # First call (miss) - slower
        start = time.perf_counter()
        analyzer.analyze(audio, sr)
        time_miss = (time.perf_counter() - start) * 1000

        # Second call (hit) - faster
        start = time.perf_counter()
        analyzer.analyze(audio, sr)
        time_hit = (time.perf_counter() - start) * 1000

        # Cache hit should be significantly faster
        assert time_hit < time_miss, f"Cache hit ({time_hit}ms) should be faster than miss ({time_miss}ms)"

    @pytest.mark.benchmark
    def test_lazy_tempo_performance(self):
        """Test lazy tempo detection performance benefit."""
        sr = 44100
        duration = 5
        t = np.arange(sr * duration) / sr
        audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

        # With tempo detection
        analyzer_eager = ContentAnalyzer(use_tempo_detection=True)
        start = time.perf_counter()
        profile_eager = analyzer_eager.analyze_content(audio)
        time_eager = (time.perf_counter() - start) * 1000

        # Without tempo detection
        analyzer_lazy = ContentAnalyzer(use_tempo_detection=False)
        start = time.perf_counter()
        profile_lazy = analyzer_lazy.analyze_content(audio)
        time_lazy = (time.perf_counter() - start) * 1000

        # Lazy should be faster (no tempo analysis)
        assert time_lazy < time_eager, f"Lazy ({time_lazy}ms) should be faster than eager ({time_eager}ms)"

    def test_preset_parameters_performance(self):
        """Test preset parameter retrieval performance."""
        # Preset retrieval should be essentially instant
        start = time.perf_counter()
        for _ in range(100):
            PresetParameters.get_preset("gentle")
        elapsed = (time.perf_counter() - start) * 1000

        # 100 retrievals should take < 10ms
        assert elapsed < 10.0, f"100 preset retrievals took {elapsed}ms (should be < 10ms)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
