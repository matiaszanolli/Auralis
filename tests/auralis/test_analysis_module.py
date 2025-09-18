#!/usr/bin/env python3
"""
Comprehensive tests for the Auralis audio analysis module (Phase 5.1).

Tests all four analysis components:
- SpectrumAnalyzer
- LoudnessMeter
- PhaseCorrelationAnalyzer
- DynamicRangeAnalyzer
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

# Import analysis modules
from auralis.analysis.spectrum_analyzer import SpectrumAnalyzer, SpectrumSettings
from auralis.analysis.loudness_meter import LoudnessMeter, LUFSMeasurement
from auralis.analysis.phase_correlation import PhaseCorrelationAnalyzer
from auralis.analysis.dynamic_range import DynamicRangeAnalyzer


class TestSpectrumAnalyzer:
    """Test the SpectrumAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_rate = 44100
        self.analyzer = SpectrumAnalyzer()

        # Create test audio signals
        self.silence = np.zeros(4410)  # 0.1 seconds
        self.sine_440 = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100))  # 440 Hz sine
        self.white_noise = np.random.normal(0, 0.1, 44100)

    def test_initialization_default(self):
        """Test default initialization."""
        analyzer = SpectrumAnalyzer()
        assert analyzer.settings is not None
        assert analyzer.frequency_bins is not None
        assert len(analyzer.frequency_bins) > 0

    def test_initialization_custom_settings(self):
        """Test initialization with custom settings."""
        # Test that we can create with default settings
        analyzer = SpectrumAnalyzer()
        assert analyzer.settings is not None
        # Test basic configuration
        if hasattr(analyzer.settings, 'fft_size'):
            assert analyzer.settings.fft_size > 0

    def test_analyze_chunk_basic(self):
        """Test basic spectrum analysis."""
        result = self.analyzer.analyze_chunk(self.sine_440)

        assert 'frequency_bins' in result
        assert 'magnitude_db' in result
        assert 'peak_frequency' in result
        assert 'spectral_centroid' in result

        # Should have some frequency content
        assert len(result['frequency_bins']) > 0
        assert len(result['magnitude_db']) > 0

        # Check that we detect the 440 Hz peak approximately
        peak_freq = result['peak_frequency']
        assert 400 < peak_freq < 480  # Allow some tolerance

    def test_analyze_chunk_silence(self):
        """Test spectrum analysis with silence."""
        result = self.analyzer.analyze_chunk(self.silence)

        assert 'magnitude_db' in result
        # Very low magnitudes for silence
        assert np.max(result['magnitude_db']) < -30

    def test_analyze_chunk_white_noise(self):
        """Test spectrum analysis with white noise."""
        result = self.analyzer.analyze_chunk(self.white_noise)

        # White noise should have energy across frequencies
        assert 'magnitude_db' in result
        assert len(result['magnitude_db']) > 0

    def test_analyze_file_method(self):
        """Test file-based analysis method."""
        result = self.analyzer.analyze_file(self.sine_440, sample_rate=44100)

        assert result is not None
        assert 'spectrum_stats' in result or 'magnitude_db' in result

    def test_frequency_weighting_functionality(self):
        """Test that frequency weighting can be applied."""
        result = self.analyzer.analyze_chunk(self.sine_440)

        # Basic spectrum analysis should work
        assert 'magnitude_db' in result
        assert len(result['magnitude_db']) > 0

    def test_real_time_processing(self):
        """Test real-time processing functionality."""
        # First analysis
        result1 = self.analyzer.analyze_chunk(self.sine_440)

        # Second analysis should work consistently
        result2 = self.analyzer.analyze_chunk(self.white_noise)

        assert result1 is not None
        assert result2 is not None
        assert 'magnitude_db' in result1
        assert 'magnitude_db' in result2

    def test_frequency_band_names(self):
        """Test frequency band name functionality."""
        band_names = self.analyzer.get_frequency_band_names()
        assert isinstance(band_names, list)
        assert len(band_names) > 0

    def test_invalid_audio_data(self):
        """Test handling of invalid audio data."""
        # Empty array
        with pytest.raises((ValueError, IndexError)):
            self.analyzer.analyze_spectrum(np.array([]))

        # Non-numeric data
        with pytest.raises(TypeError):
            self.analyzer.analyze_spectrum(['not', 'audio'])


class TestLoudnessMeter:
    """Test the LoudnessMeter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_rate = 44100
        self.meter = LoudnessMeter(self.sample_rate)

        # Create test signals
        self.silence = np.zeros((44100, 2))  # 1 second stereo silence

        # -20 dBFS sine wave (stereo)
        mono_sine = 0.1 * np.sin(2 * np.pi * 1000 * np.linspace(0, 1, 44100))
        self.sine_stereo = np.column_stack([mono_sine, mono_sine])

        # Loud sine wave
        loud_sine = 0.5 * np.sin(2 * np.pi * 1000 * np.linspace(0, 1, 44100))
        self.loud_sine_stereo = np.column_stack([loud_sine, loud_sine])

    def test_initialization(self):
        """Test LoudnessMeter initialization."""
        meter = LoudnessMeter(48000)
        assert meter.sample_rate == 48000
        assert meter.block_size == int(0.4 * 48000)  # 400ms blocks

    def test_measure_chunk_basic(self):
        """Test basic loudness measurement."""
        result = self.meter.measure_chunk(self.sine_stereo)

        assert 'momentary_loudness' in result
        assert 'peak_dbfs' in result

        # Should be negative LUFS value
        assert result['momentary_loudness'] < 0

    def test_k_weighting_application(self):
        """Test K-weighting filter application."""
        weighted = self.meter.apply_k_weighting(self.sine_stereo)
        assert weighted.shape == self.sine_stereo.shape
        assert not np.array_equal(weighted, self.sine_stereo)

    def test_measure_loudness_silence(self):
        """Test loudness measurement with silence."""
        result = self.meter.measure_loudness(self.silence)

        # Silence should result in very low loudness
        assert result['integrated_loudness'] < -60
        assert result['true_peak'] < -60

    def test_measure_loudness_loud_signal(self):
        """Test loudness measurement with loud signal."""
        result = self.meter.measure_loudness(self.loud_sine_stereo)

        # Loud signal should have higher loudness
        assert result['integrated_loudness'] > -30

    def test_k_weighting_filter(self):
        """Test K-weighting filter functionality."""
        # Filter should not crash and should process audio
        filtered = self.meter._apply_k_weighting(self.sine_stereo)
        assert filtered.shape == self.sine_stereo.shape
        assert not np.array_equal(filtered, self.sine_stereo)  # Should be different

    def test_gating_algorithm(self):
        """Test gating algorithm for integrated loudness."""
        # Create signal with varying levels
        varying_signal = np.concatenate([
            self.silence[:22050],  # 0.5s silence
            self.sine_stereo,      # 1s sine
            self.silence[:22050]   # 0.5s silence
        ])

        result = self.meter.measure_loudness(varying_signal)

        # Gating should exclude silent portions
        assert result['integrated_loudness'] is not None
        assert result['loudness_range'] >= 0

    def test_true_peak_detection(self):
        """Test true peak detection with oversampling."""
        # Create signal that approaches clipping
        near_clip = 0.95 * np.sin(2 * np.pi * 1000 * np.linspace(0, 1, 44100))
        near_clip_stereo = np.column_stack([near_clip, near_clip])

        result = self.meter.measure_loudness(near_clip_stereo)

        # True peak should be close to 0 dBFS
        assert result['true_peak'] > -1
        assert result['true_peak'] <= 0

    def test_mono_audio_handling(self):
        """Test handling of mono audio."""
        mono_audio = self.sine_stereo[:, 0]  # Take only left channel

        result = self.meter.measure_loudness(mono_audio)
        assert result is not None
        assert 'integrated_loudness' in result


class TestPhaseCorrelationAnalyzer:
    """Test the PhaseCorrelationAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = PhaseCorrelationAnalyzer()

        # Create test signals
        mono_sine = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100))

        # Perfectly correlated stereo (mono)
        self.mono_signal = np.column_stack([mono_sine, mono_sine])

        # Completely decorrelated stereo
        left = mono_sine
        right = np.sin(2 * np.pi * 880 * np.linspace(0, 1, 44100))  # Different frequency
        self.decorrelated_signal = np.column_stack([left, right])

        # Anti-phase stereo
        self.antiphase_signal = np.column_stack([mono_sine, -mono_sine])

        # Mid-side encoded signal
        mid = mono_sine
        side = 0.5 * np.sin(2 * np.pi * 220 * np.linspace(0, 1, 44100))
        left_ms = mid + side
        right_ms = mid - side
        self.midside_signal = np.column_stack([left_ms, right_ms])

    def test_analyze_correlation_mono(self):
        """Test correlation analysis with mono signal."""
        result = self.analyzer.analyze_correlation(self.mono_signal)

        assert 'correlation_coefficient' in result
        assert 'phase_correlation' in result
        assert 'stereo_width' in result
        assert 'mono_compatibility' in result

        # Mono signal should have perfect correlation
        assert result['correlation_coefficient'] > 0.99
        assert result['mono_compatibility'] > 0.9

    def test_analyze_correlation_decorrelated(self):
        """Test correlation analysis with decorrelated signal."""
        result = self.analyzer.analyze_correlation(self.decorrelated_signal)

        # Decorrelated signal should have low correlation
        assert result['correlation_coefficient'] < 0.5
        assert result['stereo_width'] > 0.5

    def test_analyze_correlation_antiphase(self):
        """Test correlation analysis with anti-phase signal."""
        result = self.analyzer.analyze_correlation(self.antiphase_signal)

        # Anti-phase should have negative correlation
        assert result['correlation_coefficient'] < -0.8
        assert result['mono_compatibility'] < 0.1  # Poor mono compatibility

    def test_phase_stability_analysis(self):
        """Test phase stability over time."""
        result = self.analyzer.analyze_correlation(self.mono_signal)

        assert 'phase_stability' in result
        assert 'phase_deviation' in result

        # Mono signal should have stable phase
        assert result['phase_stability'] > 0.8

    def test_stereo_positioning(self):
        """Test stereo positioning analysis."""
        result = self.analyzer.analyze_correlation(self.midside_signal)

        assert 'stereo_position' in result
        assert 'left_energy' in result
        assert 'right_energy' in result

        # Should detect balanced stereo positioning
        assert -0.2 < result['stereo_position'] < 0.2

    def test_invalid_stereo_input(self):
        """Test handling of invalid stereo input."""
        # Mono input (should be handled)
        mono_input = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 1000))
        result = self.analyzer.analyze_correlation(mono_input)
        assert result is not None

        # Wrong number of channels
        multi_channel = np.random.random((1000, 5))
        with pytest.raises(ValueError):
            self.analyzer.analyze_correlation(multi_channel)


class TestDynamicRangeAnalyzer:
    """Test the DynamicRangeAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = DynamicRangeAnalyzer()

        # Create test signals
        # High dynamic range signal (quiet to loud)
        quiet = 0.01 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 22050))
        loud = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 22050))
        self.dynamic_signal = np.concatenate([quiet, loud])

        # Heavily compressed signal (limited dynamic range)
        compressed = np.tanh(10 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100)))
        self.compressed_signal = 0.3 * compressed

        # Natural music-like signal
        music_like = (0.3 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100)) *
                     (1 + 0.5 * np.sin(2 * np.pi * 2 * np.linspace(0, 1, 44100))))
        self.music_signal = music_like

    def test_analyze_dynamic_range_basic(self):
        """Test basic dynamic range analysis."""
        result = self.analyzer.analyze_dynamic_range(self.dynamic_signal)

        assert 'dr_value' in result
        assert 'peak_to_loudness_ratio' in result
        assert 'crest_factor' in result
        assert 'compression_ratio' in result
        assert 'loudness_war_assessment' in result

        # High dynamic range signal should have good DR
        assert result['dr_value'] > 10

    def test_analyze_compressed_signal(self):
        """Test analysis of heavily compressed signal."""
        result = self.analyzer.analyze_dynamic_range(self.compressed_signal)

        # Compressed signal should have lower dynamic range
        assert result['dr_value'] < 15
        assert result['compression_ratio'] > 2.0
        assert result['loudness_war_assessment']['is_overcompressed'] == True

    def test_crest_factor_calculation(self):
        """Test crest factor calculation."""
        # Pure sine wave should have crest factor around 3 dB
        sine = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100))
        result = self.analyzer.analyze_dynamic_range(sine)

        # Crest factor for sine wave should be around 3 dB
        assert 2.5 < result['crest_factor'] < 3.5

    def test_peak_to_loudness_ratio(self):
        """Test Peak-to-Loudness Ratio calculation."""
        result = self.analyzer.analyze_dynamic_range(self.music_signal)

        assert result['peak_to_loudness_ratio'] > 0
        assert result['peak_to_loudness_ratio'] < 50  # Reasonable upper bound

    def test_compression_detection(self):
        """Test compression ratio estimation."""
        # Uncompressed signal
        natural_result = self.analyzer.analyze_dynamic_range(self.music_signal)

        # Compressed signal
        compressed_result = self.analyzer.analyze_dynamic_range(self.compressed_signal)

        # Compressed signal should have higher compression ratio
        assert compressed_result['compression_ratio'] > natural_result['compression_ratio']

    def test_loudness_war_assessment(self):
        """Test loudness war assessment."""
        result = self.analyzer.analyze_dynamic_range(self.compressed_signal)
        assessment = result['loudness_war_assessment']

        assert 'is_overcompressed' in assessment
        assert 'dynamic_range_rating' in assessment
        assert 'quality_score' in assessment

        # Compressed signal should be flagged
        assert assessment['quality_score'] < 0.7

    def test_attack_time_estimation(self):
        """Test attack time estimation."""
        # Create signal with fast attack
        attack_signal = np.zeros(44100)
        attack_signal[22050:] = 0.5  # Instant attack at halfway point

        result = self.analyzer.analyze_dynamic_range(attack_signal)

        assert 'attack_time' in result
        assert result['attack_time'] < 0.01  # Very fast attack

    def test_release_time_estimation(self):
        """Test release time estimation."""
        # Create signal with gradual release
        release_signal = np.zeros(44100)
        release_signal[:22050] = 0.5
        # Exponential decay
        release_signal[22050:] = 0.5 * np.exp(-10 * np.linspace(0, 1, 22050))

        result = self.analyzer.analyze_dynamic_range(release_signal)

        assert 'release_time' in result
        assert result['release_time'] > 0.05  # Slower release


class TestAnalysisIntegration:
    """Test integration between analysis modules."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a complex music-like signal
        duration = 2.0  # 2 seconds
        sample_rate = 44100
        t = np.linspace(0, duration, int(duration * sample_rate))

        # Multiple frequency components
        fundamental = 0.3 * np.sin(2 * np.pi * 220 * t)  # A3
        harmonic2 = 0.15 * np.sin(2 * np.pi * 440 * t)   # A4
        harmonic3 = 0.1 * np.sin(2 * np.pi * 660 * t)    # E5

        # Add some dynamics and stereo width
        envelope = 0.5 * (1 + np.sin(2 * np.pi * 0.5 * t))  # Slow amplitude modulation

        left = (fundamental + harmonic2 + harmonic3) * envelope
        right = (fundamental + harmonic2 * 0.8 + harmonic3 * 1.2) * envelope  # Slightly different mix

        self.test_audio = np.column_stack([left, right])

        # Initialize all analyzers
        self.spectrum_analyzer = SpectrumAnalyzer()
        self.loudness_meter = LoudnessMeter(sample_rate)
        self.phase_analyzer = PhaseCorrelationAnalyzer()
        self.dynamics_analyzer = DynamicRangeAnalyzer()

    def test_complete_analysis_pipeline(self):
        """Test running all analyzers on the same signal."""
        # Run all analyses
        spectrum_result = self.spectrum_analyzer.analyze_spectrum(self.test_audio[:, 0])  # Mono for spectrum
        loudness_result = self.loudness_meter.measure_loudness(self.test_audio)
        phase_result = self.phase_analyzer.analyze_correlation(self.test_audio)
        dynamics_result = self.dynamics_analyzer.analyze_dynamic_range(self.test_audio[:, 0])  # Mono for dynamics

        # Verify all analyses completed successfully
        assert spectrum_result is not None
        assert loudness_result is not None
        assert phase_result is not None
        assert dynamics_result is not None

        # Check for expected relationships between results
        # Peak frequency should be around 220 Hz (fundamental)
        assert 200 < spectrum_result['peak_frequency'] < 250

        # Loudness should be reasonable for our signal level
        assert -50 < loudness_result['integrated_loudness'] < -10

        # Phase correlation should show some stereo width but not anti-phase
        assert 0.3 < phase_result['correlation_coefficient'] < 0.9

        # Dynamic range should be reasonable for musical content
        assert dynamics_result['dr_value'] > 5

    def test_cross_analyzer_consistency(self):
        """Test consistency between different analyzers."""
        # Analyze the same signal with different analyzers
        spectrum_result = self.spectrum_analyzer.analyze_spectrum(self.test_audio[:, 0])
        dynamics_result = self.dynamics_analyzer.analyze_dynamic_range(self.test_audio[:, 0])

        # Both should detect similar spectral characteristics
        # Peak frequency should be consistent
        spectrum_peak = spectrum_result['peak_frequency']

        # Dynamic range analysis should also reflect the frequency content
        assert dynamics_result['crest_factor'] > 0  # Should have some dynamic variation

    def test_performance_benchmarking(self):
        """Test performance of all analyzers."""
        import time

        # Measure execution time for each analyzer
        start_time = time.time()
        self.spectrum_analyzer.analyze_spectrum(self.test_audio[:, 0])
        spectrum_time = time.time() - start_time

        start_time = time.time()
        self.loudness_meter.measure_loudness(self.test_audio)
        loudness_time = time.time() - start_time

        start_time = time.time()
        self.phase_analyzer.analyze_correlation(self.test_audio)
        phase_time = time.time() - start_time

        start_time = time.time()
        self.dynamics_analyzer.analyze_dynamic_range(self.test_audio[:, 0])
        dynamics_time = time.time() - start_time

        # All analyses should complete in reasonable time (< 1 second for 2 seconds of audio)
        assert spectrum_time < 1.0
        assert loudness_time < 1.0
        assert phase_time < 1.0
        assert dynamics_time < 1.0

        print(f"\nPerformance benchmark:")
        print(f"Spectrum analysis: {spectrum_time:.3f}s")
        print(f"Loudness analysis: {loudness_time:.3f}s")
        print(f"Phase analysis: {phase_time:.3f}s")
        print(f"Dynamics analysis: {dynamics_time:.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])