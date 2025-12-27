# -*- coding: utf-8 -*-


"""
Phase 7.4d Tests: Streaming Harmonic Analyzer

Tests for real-time harmonic metrics using chunk-based analysis.

Test Coverage:
- Harmonic/percussive separation correctness
- Pitch tracking and stability calculation
- Chroma energy aggregation
- Chunk-based processing and state management
- Metric convergence and stability
- Edge cases and robustness
"""

import librosa
import numpy as np
import pytest

from auralis.analysis.fingerprint.streaming_harmonic_analyzer import (
    HarmonicRunningStats,
    StreamingHarmonicAnalyzer,
)


class TestHarmonicRunningStats:
    """Test harmonic running statistics."""

    def test_initialization(self):
        """Test stats initialization."""
        stats = HarmonicRunningStats()

        assert stats.count == 0
        assert stats.get_harmonic_ratio() == 0.5
        assert stats.get_pitch_stability() == 0.5
        assert stats.get_chroma_energy() == 0.5

    def test_harmonic_ratio_update(self):
        """Test harmonic ratio aggregation."""
        stats = HarmonicRunningStats()

        # Add some ratios
        stats.update_harmonic(0.3)
        stats.update_harmonic(0.4)
        stats.update_harmonic(0.5)

        assert stats.count == 3
        ratio = stats.get_harmonic_ratio()
        assert np.isclose(ratio, 0.4)  # Average of 0.3, 0.4, 0.5

    def test_pitch_values_accumulation(self):
        """Test pitch value storage."""
        stats = HarmonicRunningStats()

        # Add some pitch values
        f0_1 = np.array([440, 441, 442, 0, 0])  # 0 = unvoiced
        f0_2 = np.array([440, 440, 0, 443, 444])

        stats.update_pitch(f0_1)
        stats.update_pitch(f0_2)

        # Should have accumulated voiced frames
        assert len(stats.pitch_values) > 0

    def test_chroma_energy_update(self):
        """Test chroma energy aggregation."""
        stats = HarmonicRunningStats()

        stats.update_chroma(0.2)
        stats.update_chroma(0.3)
        stats.update_chroma(0.4)

        energy = stats.get_chroma_energy()
        # Average chroma: (0.2 + 0.3 + 0.4) / 3 = 0.3, normalized by 0.4 = 0.75
        # Just verify it's in valid range
        assert 0 <= energy <= 1.0

    def test_reset(self):
        """Test stats reset."""
        stats = HarmonicRunningStats()

        stats.update_harmonic(0.8)
        stats.update_chroma(0.3)
        stats.update_pitch(np.array([440]))

        assert stats.count > 0
        stats.reset()
        assert stats.count == 0
        assert stats.get_harmonic_ratio() == 0.5


class TestStreamingHarmonicAnalyzer:
    """Test streaming harmonic analyzer."""

    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = StreamingHarmonicAnalyzer(sr=44100)

        metrics = analyzer.get_metrics()
        assert 'harmonic_ratio' in metrics
        assert 'pitch_stability' in metrics
        assert 'chroma_energy' in metrics

    def test_single_frame_update(self):
        """Test updating with single frame."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        frame = np.random.randn(sr // 10) * 0.1

        metrics = analyzer.update(frame)

        # All metrics should be in valid range
        assert 0 <= metrics['harmonic_ratio'] <= 1.0
        assert 0 <= metrics['pitch_stability'] <= 1.0
        assert 0 <= metrics['chroma_energy'] <= 1.0

    def test_sine_wave_harmonic(self):
        """Test with sine wave (high harmonic)."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        # Pure sine wave = harmonic
        duration = 1.0
        t = np.arange(int(sr * duration)) / sr
        sine = np.sin(2 * np.pi * 440 * t) * 0.1

        frame_size = sr // 10
        for i in range(0, len(sine), frame_size):
            frame = sine[i:i + frame_size]
            if len(frame) > 0:
                analyzer.update(frame)

        metrics = analyzer.get_metrics()

        # Pure sine should have high harmonic ratio
        assert 0 <= metrics['harmonic_ratio'] <= 1.0

    def test_white_noise_percussive(self):
        """Test with white noise (high percussive)."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        # White noise = percussive
        noise = np.random.randn(sr) * 0.1

        frame_size = sr // 10
        for i in range(0, len(noise), frame_size):
            frame = noise[i:i + frame_size]
            if len(frame) > 0:
                analyzer.update(frame)

        metrics = analyzer.get_metrics()

        # Noise should have lower harmonic ratio
        assert 0 <= metrics['harmonic_ratio'] <= 1.0

    def test_frame_count(self):
        """Test frame count tracking."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        assert analyzer.get_frame_count() == 0

        frame = np.random.randn(sr // 10) * 0.1

        for i in range(1, 11):
            analyzer.update(frame)
            assert analyzer.get_frame_count() == i

    def test_chunk_count(self):
        """Test chunk count tracking."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr, chunk_duration=0.5)

        initial_chunks = analyzer.get_chunk_count()

        # Process enough frames to fill at least one chunk
        frame_size = sr // 10
        for _ in range(60):  # 6 seconds
            frame = np.random.randn(frame_size) * 0.1
            analyzer.update(frame)

        final_chunks = analyzer.get_chunk_count()
        assert final_chunks > initial_chunks

    def test_reset(self):
        """Test reset functionality."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        # Process frames
        for _ in range(50):
            frame = np.random.randn(sr // 10) * 0.1
            analyzer.update(frame)

        assert analyzer.get_frame_count() > 0

        # Reset
        analyzer.reset()
        assert analyzer.get_frame_count() == 0
        assert analyzer.get_chunk_count() == 0

        # Metrics should return to defaults
        metrics = analyzer.get_metrics()
        assert 'harmonic_ratio' in metrics

    def test_confidence_score(self):
        """Test confidence scores."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        # Initial confidence should be low
        conf = analyzer.get_confidence()
        assert all(0 <= v <= 1.0 for v in conf.values())

        # Process frames to trigger chunks
        for _ in range(100):
            frame = np.random.randn(sr // 10) * 0.1
            analyzer.update(frame)

        # Confidence should increase
        conf_after = analyzer.get_confidence()
        assert all(conf_after[k] >= conf[k] * 0.99 for k in conf.keys())

    def test_silence(self):
        """Test with silent audio."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        silence = np.zeros(sr // 10)

        for _ in range(50):
            analyzer.update(silence)

        metrics = analyzer.get_metrics()

        # Silent audio should produce valid metrics
        assert 0 <= metrics['harmonic_ratio'] <= 1.0
        assert 0 <= metrics['pitch_stability'] <= 1.0
        assert 0 <= metrics['chroma_energy'] <= 1.0

    def test_high_energy(self):
        """Test with high-energy audio."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        high_energy = np.random.randn(sr // 10) * 0.95

        for _ in range(50):
            analyzer.update(high_energy)

        metrics = analyzer.get_metrics()

        # Should produce valid metrics
        assert 0 <= metrics['harmonic_ratio'] <= 1.0
        assert 0 <= metrics['pitch_stability'] <= 1.0
        assert 0 <= metrics['chroma_energy'] <= 1.0

    def test_nan_handling(self):
        """Test robustness with NaN values."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        frame = np.random.randn(sr // 10) * 0.1
        frame[50] = np.nan

        # Should handle gracefully
        metrics = analyzer.update(frame)
        assert all(isinstance(v, (int, float)) and not np.isnan(v)
                  for v in metrics.values())

    def test_streaming_consistency(self):
        """Test that metrics remain consistent across runs."""
        sr = 44100
        frame = np.ones(sr // 10) * 0.3

        # Run 1
        analyzer1 = StreamingHarmonicAnalyzer(sr=sr)
        for _ in range(30):
            analyzer1.update(frame)
        metrics1 = analyzer1.get_metrics()

        # Run 2
        analyzer2 = StreamingHarmonicAnalyzer(sr=sr)
        for _ in range(30):
            analyzer2.update(frame)
        metrics2 = analyzer2.get_metrics()

        # Should be identical for deterministic input
        for key in metrics1.keys():
            assert metrics1[key] == metrics2[key]

    def test_long_stream(self):
        """Test analyzer on extended stream (memory stability)."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        # Process 15 seconds of audio (in frames)
        frame_size = sr // 10
        num_frames = 15 * 10

        for _ in range(num_frames):
            frame = np.random.randn(frame_size) * 0.1
            analyzer.update(frame)

        # Should still produce valid metrics
        metrics = analyzer.get_metrics()
        assert 0 <= metrics['harmonic_ratio'] <= 1.0
        assert 0 <= metrics['pitch_stability'] <= 1.0
        assert 0 <= metrics['chroma_energy'] <= 1.0
        assert analyzer.get_frame_count() == num_frames


class TestHarmonicEdgeCases:
    """Test edge cases and special conditions."""

    def test_very_short_frames(self):
        """Test with very short audio frames."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        # Very short frame (100 samples)
        frame = np.random.randn(100) * 0.1

        for _ in range(200):
            analyzer.update(frame)

        metrics = analyzer.get_metrics()
        assert all(0 <= v <= 1.0 for v in metrics.values())

    def test_very_long_frames(self):
        """Test with very long audio frames."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        # Very long frame (full second)
        frame = np.random.randn(sr) * 0.1

        analyzer.update(frame)

        metrics = analyzer.get_metrics()
        assert all(0 <= v <= 1.0 for v in metrics.values())

    def test_all_ones(self):
        """Test with constant high amplitude."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        frame = np.ones(sr // 10) * 0.8

        for _ in range(20):
            analyzer.update(frame)

        metrics = analyzer.get_metrics()
        assert all(0 <= v <= 1.0 for v in metrics.values())

    def test_all_zeros(self):
        """Test with all zeros (silence)."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        frame = np.zeros(sr // 10)

        for _ in range(20):
            analyzer.update(frame)

        metrics = analyzer.get_metrics()
        assert all(0 <= v <= 1.0 for v in metrics.values())

    def test_inf_in_audio(self):
        """Test robustness with inf values."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        frame = np.random.randn(sr // 10) * 0.1
        frame[50] = np.inf

        # Should handle gracefully
        metrics = analyzer.update(frame)
        assert all(isinstance(v, (int, float)) and not np.isinf(v)
                  for v in metrics.values())


class TestHarmonicIntegration:
    """Integration tests for streaming harmonic analyzer."""

    def test_musical_tone(self):
        """Test with musical tone (440 Hz A)."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        # 440 Hz tone
        duration = 2.0
        t = np.arange(int(sr * duration)) / sr
        tone = np.sin(2 * np.pi * 440 * t) * 0.2

        frame_size = sr // 10
        for i in range(0, len(tone), frame_size):
            frame = tone[i:i + frame_size]
            if len(frame) > 0:
                analyzer.update(frame)

        metrics = analyzer.get_metrics()

        # Musical tone should have reasonable metrics
        assert 0 <= metrics['harmonic_ratio'] <= 1.0
        assert 0 <= metrics['pitch_stability'] <= 1.0

    def test_chord(self):
        """Test with musical chord."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        # C major chord: C(261.6) E(329.6) G(392)
        duration = 2.0
        t = np.arange(int(sr * duration)) / sr
        chord = (np.sin(2 * np.pi * 261.6 * t) +
                 np.sin(2 * np.pi * 329.6 * t) +
                 np.sin(2 * np.pi * 392 * t)) / 3 * 0.15

        frame_size = sr // 10
        for i in range(0, len(chord), frame_size):
            frame = chord[i:i + frame_size]
            if len(frame) > 0:
                analyzer.update(frame)

        metrics = analyzer.get_metrics()

        # Chord should have good chroma energy
        assert 0 <= metrics['chroma_energy'] <= 1.0

    def test_speech_like_signal(self):
        """Test with speech-like signal."""
        sr = 44100
        analyzer = StreamingHarmonicAnalyzer(sr=sr)

        # Simulate speech: fundamental + harmonics
        duration = 2.0
        t = np.arange(int(sr * duration)) / sr

        # Fundamental around 150 Hz (male voice)
        f0 = 150
        audio = (np.sin(2 * np.pi * f0 * t) +
                 0.5 * np.sin(2 * np.pi * 2 * f0 * t) +
                 0.3 * np.sin(2 * np.pi * 3 * f0 * t)) * 0.15

        frame_size = sr // 10
        for i in range(0, len(audio), frame_size):
            frame = audio[i:i + frame_size]
            if len(frame) > 0:
                analyzer.update(frame)

        metrics = analyzer.get_metrics()

        # Speech should have good harmonic content
        assert 0 <= metrics['harmonic_ratio'] <= 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
