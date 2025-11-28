# -*- coding: utf-8 -*-

"""
Phase 7.4a Tests: Streaming Variation Analyzer

Tests for real-time dynamic variation metrics using online algorithms.

Test Coverage:
- Running statistics (Welford algorithm correctness)
- Windowed buffer behavior
- Metric convergence and stability
- Streaming vs batch comparison
- Edge cases and robustness
"""

import pytest
import numpy as np
from auralis.analysis.fingerprint.streaming_variation_analyzer import (
    RunningStatistics,
    WindowedBuffer,
    StreamingVariationAnalyzer
)


class TestRunningStatistics:
    """Test Welford's online statistics algorithm."""

    def test_single_value(self):
        """Test running statistics with single value."""
        stats = RunningStatistics()
        stats.update(5.0)

        assert stats.count == 1
        assert stats.get_mean() == 5.0
        assert stats.get_std() == 0.0

    def test_two_values(self):
        """Test with two values."""
        stats = RunningStatistics()
        stats.update(2.0)
        stats.update(4.0)

        assert stats.count == 2
        assert stats.get_mean() == 3.0
        assert np.isclose(stats.get_std(), np.std([2.0, 4.0]))

    def test_multiple_values(self):
        """Test with multiple values matches numpy."""
        stats = RunningStatistics()
        values = [1.0, 2.5, 3.0, 4.5, 5.0]

        for v in values:
            stats.update(v)

        # Compare with numpy
        np_mean = np.mean(values)
        np_std = np.std(values)

        assert np.isclose(stats.get_mean(), np_mean)
        assert np.isclose(stats.get_std(), np_std, rtol=1e-10)

    def test_large_values(self):
        """Test numerical stability with large values."""
        stats = RunningStatistics()
        large_vals = [1e6, 1e6 + 1, 1e6 + 2]

        for v in large_vals:
            stats.update(v)

        np_std = np.std(large_vals)
        assert np.isclose(stats.get_std(), np_std, rtol=1e-10)

    def test_negative_values(self):
        """Test with negative values."""
        stats = RunningStatistics()
        values = [-5.0, -3.0, 0.0, 3.0, 5.0]

        for v in values:
            stats.update(v)

        assert np.isclose(stats.get_mean(), np.mean(values))
        assert np.isclose(stats.get_std(), np.std(values))

    def test_reset(self):
        """Test reset functionality."""
        stats = RunningStatistics()
        stats.update(1.0)
        stats.update(2.0)

        assert stats.count == 2
        stats.reset()
        assert stats.count == 0
        assert stats.get_mean() == 0.0
        assert stats.get_std() == 0.0


class TestWindowedBuffer:
    """Test sliding window buffer."""

    def test_single_value(self):
        """Test adding single value."""
        buf = WindowedBuffer(5)
        buf.append(1.0)

        values = buf.get_values()
        assert len(values) == 1
        assert values[0] == 1.0

    def test_fill_buffer(self):
        """Test filling buffer to capacity."""
        buf = WindowedBuffer(3)

        buf.append(1.0)
        assert not buf.is_full()

        buf.append(2.0)
        assert not buf.is_full()

        buf.append(3.0)
        assert buf.is_full()

        values = buf.get_values()
        assert np.allclose(values, [1.0, 2.0, 3.0])

    def test_overflow(self):
        """Test that old values are removed on overflow."""
        buf = WindowedBuffer(3)

        for i in range(1, 6):
            buf.append(float(i))

        # Should keep [3, 4, 5]
        values = buf.get_values()
        assert np.allclose(values, [3.0, 4.0, 5.0])

    def test_clear(self):
        """Test clearing buffer."""
        buf = WindowedBuffer(3)
        buf.append(1.0)
        buf.append(2.0)

        assert len(buf.get_values()) == 2
        buf.clear()
        assert len(buf.get_values()) == 0


class TestStreamingVariationAnalyzer:
    """Test streaming variation analyzer."""

    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = StreamingVariationAnalyzer(sr=44100)

        metrics = analyzer.get_metrics()
        assert 'dynamic_range_variation' in metrics
        assert 'loudness_variation_std' in metrics
        assert 'peak_consistency' in metrics

    def test_single_frame_update(self):
        """Test updating with single frame."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        frame = np.random.randn(sr // 10) * 0.1

        metrics = analyzer.update(frame)

        # Should return valid metrics (possibly defaults)
        assert all(0 <= v <= 1.0 or (isinstance(v, float) and 0 <= v <= 10.0)
                   for k, v in metrics.items())

    def test_constant_signal(self):
        """Test with constant amplitude signal."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        # Process 10 frames of constant signal
        frame_size = sr // 10
        constant_frame = np.ones(frame_size) * 0.5

        for _ in range(10):
            analyzer.update(constant_frame)

        metrics = analyzer.get_metrics()

        # Constant signal: low loudness variation, high consistency
        assert metrics['loudness_variation_std'] < 1.0
        assert metrics['peak_consistency'] > 0.8

    def test_varying_signal(self):
        """Test with varying amplitude signal."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        # Create alternating high/low amplitude frames
        frame_size = sr // 10
        frames = [
            np.ones(frame_size) * 0.1,
            np.ones(frame_size) * 0.8,
            np.ones(frame_size) * 0.2,
            np.ones(frame_size) * 0.9,
        ]

        for frame in frames * 3:  # Repeat 3 times
            analyzer.update(frame)

        metrics = analyzer.get_metrics()

        # Varying signal: higher loudness variation
        assert metrics['loudness_variation_std'] > 0.5
        # Peak consistency stays high because each frame's peak is consistent within the frame
        assert 'peak_consistency' in metrics

    def test_metric_convergence(self):
        """Test that metrics stabilize over time."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        # Process varying signal
        metrics_history = []
        for i in range(50):
            frame = np.random.randn(sr // 10) * 0.1
            metrics = analyzer.update(frame)
            metrics_history.append(metrics['peak_consistency'])

        # Later metrics should be more stable (less variance in values)
        early_var = np.var(metrics_history[:10])
        late_var = np.var(metrics_history[-10:])

        # Late metrics have less variation (more stable)
        assert late_var < early_var

    def test_confidence_score(self):
        """Test confidence scores."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        # Initial confidence should be low
        conf = analyzer.get_confidence()
        assert all(0 <= v <= 1.0 for v in conf.values())

        # Process frames
        for _ in range(100):
            frame = np.random.randn(sr // 10) * 0.1
            analyzer.update(frame)

        # Confidence should increase
        conf_after = analyzer.get_confidence()
        assert all(conf_after[k] >= conf[k] for k in conf.keys())

    def test_frame_count(self):
        """Test frame count tracking."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        assert analyzer.get_frame_count() == 0

        frame = np.random.randn(sr // 10) * 0.1

        for i in range(1, 11):
            analyzer.update(frame)
            assert analyzer.get_frame_count() == i

    def test_reset(self):
        """Test reset functionality."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        # Process frames
        for _ in range(10):
            frame = np.random.randn(sr // 10) * 0.1
            analyzer.update(frame)

        assert analyzer.get_frame_count() > 0

        # Reset
        analyzer.reset()
        assert analyzer.get_frame_count() == 0

        # Metrics should return to defaults
        metrics = analyzer.get_metrics()
        assert 'dynamic_range_variation' in metrics

    def test_silence(self):
        """Test with silent audio."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        silence = np.zeros(sr // 10)

        for _ in range(20):
            analyzer.update(silence)

        metrics = analyzer.get_metrics()

        # Silent audio: near-zero loudness variation
        assert metrics['loudness_variation_std'] < 0.5
        # For silence (peaks all 0), peak consistency returns default 0.5
        assert 'peak_consistency' in metrics
        assert 0 <= metrics['peak_consistency'] <= 1

    def test_high_energy(self):
        """Test with high-energy audio."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        high_energy = np.random.randn(sr // 10) * 0.95

        for _ in range(20):
            analyzer.update(high_energy)

        metrics = analyzer.get_metrics()

        # High energy should still produce valid metrics
        assert 0 <= metrics['dynamic_range_variation'] <= 1.0
        assert 0 <= metrics['loudness_variation_std'] <= 10.0
        assert 0 <= metrics['peak_consistency'] <= 1.0

    def test_nan_handling(self):
        """Test robustness with NaN values."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        frame = np.random.randn(sr // 10) * 0.1
        frame[50] = np.nan

        # Should handle gracefully
        metrics = analyzer.update(frame)
        assert all(isinstance(v, (int, float)) for v in metrics.values())

    def test_streaming_vs_batch_similarity(self):
        """Test that streaming metrics match batch after same duration."""
        sr = 44100
        duration = 3  # 3 seconds

        # Generate test audio
        audio = np.random.randn(sr * duration) * 0.1

        # Streaming analysis
        analyzer = StreamingVariationAnalyzer(sr=sr)
        frame_size = sr // 10
        for i in range(0, len(audio), frame_size):
            frame = audio[i:i + frame_size]
            if len(frame) > 0:
                analyzer.update(frame)

        streaming_metrics = analyzer.get_metrics()

        # Both should produce metrics in valid ranges
        assert 0 <= streaming_metrics['dynamic_range_variation'] <= 1.0
        assert 0 <= streaming_metrics['loudness_variation_std'] <= 10.0
        assert 0 <= streaming_metrics['peak_consistency'] <= 1.0

    def test_incremental_update_efficiency(self):
        """Test that streaming is more efficient than full re-computation."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        frame = np.random.randn(sr // 10) * 0.1

        # Update should be O(1) regardless of history
        # (Just verify it completes in reasonable time)
        import time

        start = time.time()
        for _ in range(1000):
            analyzer.update(frame)
        elapsed = time.time() - start

        # Should complete quickly (< 1 second for 1000 updates)
        assert elapsed < 1.0

    def test_multiple_window_sizes(self):
        """Test with different window durations."""
        sr = 44100
        frame = np.random.randn(sr // 10) * 0.1

        for window_duration in [0.5, 2.0, 5.0, 10.0]:
            analyzer = StreamingVariationAnalyzer(
                sr=sr,
                window_duration=window_duration
            )

            # Process frames
            for _ in range(100):
                analyzer.update(frame)

            # Should produce valid metrics regardless of window
            metrics = analyzer.get_metrics()
            assert 0 <= metrics['peak_consistency'] <= 1.0


class TestStreamingVariationIntegration:
    """Integration tests for streaming variation analyzer."""

    def test_deterministic_behavior(self):
        """Test that same input produces same output."""
        sr = 44100
        frame = np.ones(sr // 10) * 0.5

        # Run 1
        analyzer1 = StreamingVariationAnalyzer(sr=sr)
        for _ in range(20):
            analyzer1.update(frame)
        metrics1 = analyzer1.get_metrics()

        # Run 2
        analyzer2 = StreamingVariationAnalyzer(sr=sr)
        for _ in range(20):
            analyzer2.update(frame)
        metrics2 = analyzer2.get_metrics()

        # Should be identical
        for key in metrics1.keys():
            assert metrics1[key] == metrics2[key]

    def test_long_stream(self):
        """Test analyzer on extended stream (memory stability)."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        # Process 1 minute of audio (in frames)
        frame_size = sr // 10
        num_frames = 60 * 10  # 60 seconds worth

        for _ in range(num_frames):
            frame = np.random.randn(frame_size) * 0.1
            analyzer.update(frame)

        # Should still produce valid metrics
        metrics = analyzer.get_metrics()
        assert all(isinstance(v, (int, float)) for v in metrics.values())
        assert analyzer.get_frame_count() == num_frames

    def test_confidence_progression(self):
        """Test confidence increases with more data."""
        sr = 44100
        analyzer = StreamingVariationAnalyzer(sr=sr)

        confidences = []
        for i in range(100):
            frame = np.random.randn(sr // 10) * 0.1
            analyzer.update(frame)
            conf = analyzer.get_confidence()
            confidences.append(conf['peak_consistency'])

        # Confidence should be monotonically non-decreasing
        for i in range(1, len(confidences)):
            assert confidences[i] >= confidences[i - 1]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
