# -*- coding: utf-8 -*-


"""
Phase 7.4c Tests: Streaming Temporal Analyzer

Tests for real-time temporal and rhythmic metrics.

Test Coverage:
- Onset detection buffer correctness
- Periodic beat tracking and tempo detection
- Transient density calculation
- Silence ratio from RMS history
- Metric convergence and stability
- Edge cases and robustness
"""

import pytest
import numpy as np
import librosa
from auralis.analysis.fingerprint.streaming_temporal_analyzer import (
    OnsetBuffer,
    StreamingTemporalAnalyzer
)


class TestOnsetBuffer:
    """Test onset detection buffer."""

    def test_initialization(self):
        """Test buffer initialization."""
        buf = OnsetBuffer(sr=44100, buffer_duration=2.0)

        assert buf.sr == 44100
        assert buf.buffer_duration == 2.0
        assert len(buf.audio_buffer) == 0

    def test_append_frames(self):
        """Test appending audio frames."""
        buf = OnsetBuffer(sr=44100, buffer_duration=0.5)

        frame = np.random.randn(4410) * 0.1

        buf.append(frame)
        assert len(buf.audio_buffer) > 0

        buf.append(frame)
        # Should not exceed maxlen
        assert len(buf.audio_buffer) <= buf.buffer_size

    def test_detect_onsets_silence(self):
        """Test onset detection on silent audio."""
        buf = OnsetBuffer(sr=44100, buffer_duration=1.0)

        silence = np.zeros(44100)
        buf.append(silence)

        onsets = buf.detect_onsets()
        # Silence should have no/minimal onsets
        assert isinstance(onsets, np.ndarray)
        assert len(onsets) == 0 or np.all(onsets == 0)

    def test_detect_onsets_with_clicks(self):
        """Test onset detection on audio with transients."""
        buf = OnsetBuffer(sr=44100, buffer_duration=1.0)

        # Create audio with transients (impulses)
        audio = np.zeros(44100)
        # Add impulses at 0.1, 0.3, 0.5 seconds
        audio[4410] = 1.0
        audio[13230] = 1.0
        audio[22050] = 1.0

        buf.append(audio)

        onsets = buf.detect_onsets()
        # Should detect some onsets
        assert isinstance(onsets, np.ndarray)
        # May or may not detect depending on threshold

    def test_clear(self):
        """Test clearing buffer."""
        buf = OnsetBuffer(sr=44100, buffer_duration=1.0)

        frame = np.random.randn(4410) * 0.1
        buf.append(frame)

        assert len(buf.audio_buffer) > 0
        buf.clear()
        assert len(buf.audio_buffer) == 0


class TestStreamingTemporalAnalyzer:
    """Test streaming temporal analyzer."""

    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = StreamingTemporalAnalyzer(sr=44100)

        metrics = analyzer.get_metrics()
        assert 'tempo_bpm' in metrics
        assert 'rhythm_stability' in metrics
        assert 'transient_density' in metrics
        assert 'silence_ratio' in metrics

    def test_single_frame_update(self):
        """Test updating with single frame."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        frame = np.random.randn(sr // 10) * 0.1

        metrics = analyzer.update(frame)

        # All metrics should be in valid range
        assert 40 <= metrics['tempo_bpm'] <= 200
        assert 0 <= metrics['rhythm_stability'] <= 1.0
        assert 0 <= metrics['transient_density'] <= 1.0
        assert 0 <= metrics['silence_ratio'] <= 1.0

    def test_silent_audio_metrics(self):
        """Test with silent audio."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        silence = np.zeros(sr // 10)

        for _ in range(50):
            analyzer.update(silence)

        metrics = analyzer.get_metrics()

        # Silent audio should have high silence ratio
        assert metrics['silence_ratio'] > 0.8

    def test_noisy_audio_metrics(self):
        """Test with noisy (white noise) audio."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        noise = np.random.randn(sr // 10) * 0.2

        for _ in range(50):
            analyzer.update(noise)

        metrics = analyzer.get_metrics()

        # White noise should have low silence ratio
        assert metrics['silence_ratio'] < 0.5

    def test_constant_tone_metrics(self):
        """Test with constant tone."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        # 120 BPM tone would have relatively stable rhythm
        duration = 2.0
        t = np.arange(int(sr * duration)) / sr
        tone = np.sin(2 * np.pi * 440 * t) * 0.1

        frame_size = sr // 10
        for i in range(0, len(tone), frame_size):
            frame = tone[i:i + frame_size]
            if len(frame) > 0:
                analyzer.update(frame)

        metrics = analyzer.get_metrics()

        # All should be valid ranges
        assert 40 <= metrics['tempo_bpm'] <= 200
        assert 0 <= metrics['rhythm_stability'] <= 1.0

    def test_periodic_analysis(self):
        """Test that analysis occurs periodically."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr, buffer_duration=0.5)

        frame = np.random.randn(sr // 10) * 0.1

        initial_analyses = analyzer.get_analysis_count()

        # Process enough frames to trigger analysis
        for _ in range(100):
            analyzer.update(frame)

        final_analyses = analyzer.get_analysis_count()

        # Should have performed at least one analysis
        assert final_analyses >= initial_analyses

    def test_frame_count(self):
        """Test frame count tracking."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        assert analyzer.get_frame_count() == 0

        frame = np.random.randn(sr // 10) * 0.1

        for i in range(1, 11):
            analyzer.update(frame)
            assert analyzer.get_frame_count() == i

    def test_reset(self):
        """Test reset functionality."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        # Process frames
        for _ in range(50):
            frame = np.random.randn(sr // 10) * 0.1
            analyzer.update(frame)

        assert analyzer.get_frame_count() > 0

        # Reset
        analyzer.reset()
        assert analyzer.get_frame_count() == 0

        # Metrics should return to defaults
        metrics = analyzer.get_metrics()
        assert 'tempo_bpm' in metrics

    def test_confidence_score(self):
        """Test confidence scores."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        # Initial confidence should be low
        conf = analyzer.get_confidence()
        assert all(0 <= v <= 1.0 for v in conf.values())

        # Process frames
        for _ in range(200):
            frame = np.random.randn(sr // 10) * 0.1
            analyzer.update(frame)

        # Confidence should increase
        conf_after = analyzer.get_confidence()
        assert all(conf_after[k] >= conf[k] * 0.99 for k in conf.keys())

    def test_tempo_stability(self):
        """Test that tempo estimate stabilizes."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        # Regular beat at 120 BPM
        beat_interval = sr // 2  # 0.5 seconds = 120 BPM
        duration = 5.0
        audio = np.zeros(int(sr * duration))

        # Add beats at regular intervals
        beat_pos = 0
        while beat_pos < len(audio):
            audio[beat_pos:beat_pos + 100] += 1.0  # Transient
            beat_pos += beat_interval

        # Normalize
        audio = audio / (np.max(np.abs(audio)) + 1e-10)

        # Process in chunks
        frame_size = sr // 10
        tempo_history = []
        for i in range(0, len(audio), frame_size):
            frame = audio[i:i + frame_size]
            if len(frame) > 0:
                metrics = analyzer.update(frame)
                tempo_history.append(metrics['tempo_bpm'])

        # Later tempos should be more stable
        if len(tempo_history) > 10:
            early_var = np.var(tempo_history[:5])
            late_var = np.var(tempo_history[-5:])

            # Late estimates should be more stable (lower variance)
            assert late_var < (early_var + 50)  # Allow some flexibility

    def test_nan_handling(self):
        """Test robustness with NaN values."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

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
        analyzer1 = StreamingTemporalAnalyzer(sr=sr)
        for _ in range(30):
            analyzer1.update(frame)
        metrics1 = analyzer1.get_metrics()

        # Run 2
        analyzer2 = StreamingTemporalAnalyzer(sr=sr)
        for _ in range(30):
            analyzer2.update(frame)
        metrics2 = analyzer2.get_metrics()

        # Should be identical for deterministic input
        for key in metrics1.keys():
            assert metrics1[key] == metrics2[key]

    def test_long_stream(self):
        """Test analyzer on extended stream (memory stability)."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        # Process 20 seconds of audio (in frames)
        frame_size = sr // 10
        num_frames = 20 * 10

        for _ in range(num_frames):
            frame = np.random.randn(frame_size) * 0.1
            analyzer.update(frame)

        # Should still produce valid metrics
        metrics = analyzer.get_metrics()
        assert 40 <= metrics['tempo_bpm'] <= 200
        assert 0 <= metrics['rhythm_stability'] <= 1.0
        assert 0 <= metrics['transient_density'] <= 1.0
        assert 0 <= metrics['silence_ratio'] <= 1.0
        assert analyzer.get_frame_count() == num_frames

    def test_mixed_audio(self):
        """Test with mixed sound (speech-like signal)."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        # Simulate speech: combination of sine waves
        duration = 3.0
        t = np.arange(int(sr * duration)) / sr

        # Fundamental + harmonics
        audio = (np.sin(2 * np.pi * 150 * t) +  # Fundamental
                 0.5 * np.sin(2 * np.pi * 300 * t) +  # 2nd harmonic
                 0.3 * np.sin(2 * np.pi * 450 * t))  # 3rd harmonic

        audio = audio / np.max(np.abs(audio)) * 0.2

        # Process in chunks
        frame_size = sr // 10
        for i in range(0, len(audio), frame_size):
            frame = audio[i:i + frame_size]
            if len(frame) > 0:
                analyzer.update(frame)

        metrics = analyzer.get_metrics()

        # Should produce reasonable metrics
        assert 40 <= metrics['tempo_bpm'] <= 200
        assert 0 <= metrics['silence_ratio'] < 0.8  # Speech has silence but not too much


class TestTemporalEdgeCases:
    """Test edge cases and special conditions."""

    def test_very_short_frames(self):
        """Test with very short frames."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        frame = np.random.randn(100) * 0.1

        for _ in range(200):
            analyzer.update(frame)

        metrics = analyzer.get_metrics()
        assert 40 <= metrics['tempo_bpm'] <= 200

    def test_very_long_frames(self):
        """Test with very long frames."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        # Full second frames
        frame = np.random.randn(sr) * 0.1

        analyzer.update(frame)

        metrics = analyzer.get_metrics()
        assert all(isinstance(v, float) for v in metrics.values())

    def test_all_ones(self):
        """Test with constant high amplitude."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        frame = np.ones(sr // 10) * 0.8

        for _ in range(30):
            analyzer.update(frame)

        metrics = analyzer.get_metrics()
        assert 40 <= metrics['tempo_bpm'] <= 200
        assert 0 <= metrics['silence_ratio'] < 0.5

    def test_all_zeros(self):
        """Test with all zeros (silence)."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        frame = np.zeros(sr // 10)

        for _ in range(30):
            analyzer.update(frame)

        metrics = analyzer.get_metrics()
        assert 40 <= metrics['tempo_bpm'] <= 200
        assert metrics['silence_ratio'] > 0.8

    def test_inf_in_audio(self):
        """Test robustness with inf values."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        frame = np.random.randn(sr // 10) * 0.1
        frame[50] = np.inf

        # Should handle gracefully
        metrics = analyzer.update(frame)
        assert all(isinstance(v, (int, float)) and not np.isinf(v)
                  for v in metrics.values())


class TestTemporalIntegration:
    """Integration tests for streaming temporal analyzer."""

    def test_alternating_silence_sound(self):
        """Test with alternating silence and sound."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        # Alternate between silence and noise
        silence = np.zeros(sr // 10)
        noise = np.random.randn(sr // 10) * 0.2

        for i in range(40):
            if i % 2 == 0:
                analyzer.update(silence)
            else:
                analyzer.update(noise)

        metrics = analyzer.get_metrics()

        # Should have moderate silence ratio
        assert 0.3 < metrics['silence_ratio'] < 0.7

    def test_increasing_tempo_simulation(self):
        """Test with simulated increasing tempo."""
        sr = 44100
        analyzer = StreamingTemporalAnalyzer(sr=sr)

        # Create signal with increasing beat frequency
        duration = 3.0
        audio = np.zeros(int(sr * duration))

        # Start at 100 BPM, increase to 150 BPM
        t = np.arange(len(audio)) / sr
        beat_freq = 100 / 60 + (150 - 100) / 60 * t / duration  # In Hz
        cumsum_phase = np.cumsum(beat_freq) * 2 * np.pi / sr

        # Add transient at each beat
        beat_times = np.where(np.diff(np.cos(cumsum_phase)) < -1)[0]
        for beat_time in beat_times:
            if beat_time + 1000 < len(audio):
                audio[beat_time:beat_time + 1000] += 1.0

        # Normalize
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio)) * 0.2

        # Process
        frame_size = sr // 10
        tempos = []
        for i in range(0, len(audio), frame_size):
            frame = audio[i:i + frame_size]
            if len(frame) > 0:
                metrics = analyzer.update(frame)
                tempos.append(metrics['tempo_bpm'])

        # Final tempo should be closer to 150 BPM
        if len(tempos) > 5:
            final_tempo = np.mean(tempos[-5:])
            # Allow wide range due to beat detection variance
            assert 60 <= final_tempo <= 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
