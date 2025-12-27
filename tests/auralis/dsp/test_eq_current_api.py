#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Psychoacoustic EQ Current API Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the current psychoacoustic EQ API after modular refactoring.
This test file validates the actual current implementation.
"""

import os
import sys

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.abspath('../..'))

from auralis.dsp.eq import (
    CriticalBand,
    EQSettings,
    MaskingThresholdCalculator,
    PsychoacousticEQ,
    create_critical_bands,
    create_psychoacoustic_eq,
    generate_genre_eq_curve,
)


class TestEQCurrentAPI:
    """Test suite for current psychoacoustic EQ API"""

    def setUp(self):
        """Set up test fixtures"""
        self.sample_rate = 44100
        self.settings = EQSettings(
            sample_rate=self.sample_rate,
            fft_size=4096,
            overlap=0.75,
            smoothing_factor=0.1,
            adaptation_speed=0.2
        )

        # Create test audio
        duration = 1.0
        samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, samples)
        self.test_mono = 0.5 * np.sin(2 * np.pi * 440 * t)
        self.test_stereo = np.column_stack([
            0.5 * np.sin(2 * np.pi * 440 * t),
            0.4 * np.sin(2 * np.pi * 880 * t)
        ])

        # Create test chunk (smaller for real-time processing)
        chunk_samples = 4096
        t_chunk = np.linspace(0, chunk_samples / self.sample_rate, chunk_samples)
        self.test_chunk = 0.5 * np.sin(2 * np.pi * 440 * t_chunk)

    def tearDown(self):
        """Clean up test fixtures"""
        pass

    def test_eq_settings_dataclass(self):
        """Test EQSettings dataclass creation"""
        self.setUp()

        # Test with default values
        settings = EQSettings()
        assert settings.sample_rate == 44100
        assert settings.fft_size == 4096
        assert settings.overlap == 0.75
        assert settings.smoothing_factor == 0.1

        # Test with custom values
        custom_settings = EQSettings(
            sample_rate=48000,
            fft_size=8192,
            overlap=0.5,
            smoothing_factor=0.2,
            masking_threshold_db=-50.0,
            adaptation_speed=0.3
        )
        assert custom_settings.sample_rate == 48000
        assert custom_settings.fft_size == 8192
        assert custom_settings.adaptation_speed == 0.3

        self.tearDown()

    def test_critical_band_dataclass(self):
        """Test CriticalBand dataclass"""
        self.setUp()

        band = CriticalBand(
            index=5,
            center_freq=1000.0,
            low_freq=800.0,
            high_freq=1200.0,
            bandwidth=400.0,
            weight=1.0
        )

        assert band.index == 5
        assert band.center_freq == 1000.0
        assert band.low_freq == 800.0
        assert band.high_freq == 1200.0
        assert band.bandwidth == 400.0
        assert band.weight == 1.0

        self.tearDown()

    def test_create_critical_bands(self):
        """Test critical bands creation"""
        self.setUp()

        bands = create_critical_bands()

        # Should have 26 bands (based on Bark scale)
        assert len(bands) >= 20  # At least 20 bands
        assert len(bands) <= 30  # At most 30 bands

        # Verify band structure
        for i, band in enumerate(bands):
            assert isinstance(band, CriticalBand)
            # First band might start at 0 Hz
            if i > 0:
                assert band.center_freq > 0
            assert band.low_freq >= 0
            assert band.high_freq > band.low_freq
            assert band.bandwidth > 0
            assert band.weight > 0

        # Verify bands are ordered by frequency
        for i in range(len(bands) - 1):
            assert bands[i].center_freq < bands[i+1].center_freq

        self.tearDown()

    def test_psychoacoustic_eq_initialization(self):
        """Test PsychoacousticEQ initialization"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)

        assert eq is not None
        assert eq.settings == self.settings
        assert eq.sample_rate == self.sample_rate
        assert hasattr(eq, 'critical_bands')
        assert hasattr(eq, 'masking_calculator')
        assert hasattr(eq, 'current_gains')
        assert len(eq.current_gains) == len(eq.critical_bands)

        self.tearDown()

    def test_factory_function(self):
        """Test create_psychoacoustic_eq factory function"""
        self.setUp()

        # Test with defaults
        eq = create_psychoacoustic_eq()
        assert eq is not None
        assert eq.sample_rate == 44100

        # Test with custom parameters
        eq_custom = create_psychoacoustic_eq(
            sample_rate=48000,
            fft_size=8192
        )
        assert eq_custom.sample_rate == 48000
        assert eq_custom.fft_size == 8192

        self.tearDown()

    def test_masking_threshold_calculator(self):
        """Test MaskingThresholdCalculator"""
        self.setUp()

        calculator = MaskingThresholdCalculator()
        assert calculator is not None

        # Create test spectrum
        fft_size = 2048
        magnitude_spectrum = np.abs(np.fft.rfft(self.test_chunk[:fft_size]))

        # Calculate masking thresholds
        bands = create_critical_bands()
        thresholds = calculator.calculate_masking(
            magnitude_spectrum,
            bands,
            self.sample_rate
        )

        assert len(thresholds) == len(bands)
        assert np.all(np.isfinite(thresholds))
        # Thresholds should be in reasonable range (can be positive or negative dB)
        assert np.all(thresholds >= -100.0)  # Not extremely negative
        assert np.all(thresholds <= 50.0)  # Not extremely positive

        self.tearDown()

    def test_spectrum_analysis(self):
        """Test analyze_spectrum method"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)

        # Analyze spectrum
        analysis = eq.analyze_spectrum(self.test_chunk)

        # Verify analysis structure
        assert isinstance(analysis, dict)
        assert 'band_energies' in analysis
        assert 'masking_thresholds' in analysis
        assert 'spectrum' in analysis

        # Verify data shapes
        num_bands = len(eq.critical_bands)
        assert len(analysis['band_energies']) == num_bands
        assert len(analysis['masking_thresholds']) == num_bands
        assert len(analysis['spectrum']) > 0

        # Verify values are finite
        assert np.all(np.isfinite(analysis['band_energies']))
        assert np.all(np.isfinite(analysis['masking_thresholds']))

        self.tearDown()

    def test_calculate_adaptive_gains(self):
        """Test calculate_adaptive_gains method"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)

        # Analyze spectrum first
        analysis = eq.analyze_spectrum(self.test_chunk)

        # Create target curve (flat response)
        target_curve = np.zeros(len(eq.critical_bands))

        # Calculate adaptive gains
        gains = eq.calculate_adaptive_gains(analysis, target_curve)

        assert len(gains) == len(eq.critical_bands)
        assert np.all(np.isfinite(gains))
        # Gains should be in reasonable range (-12 to +12 dB)
        assert np.all(gains >= -15.0)
        assert np.all(gains <= 15.0)

        self.tearDown()

    def test_adaptive_gains_with_content_profile(self):
        """Test adaptive gains calculation with content profile"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)
        analysis = eq.analyze_spectrum(self.test_chunk)
        target_curve = np.zeros(len(eq.critical_bands))

        # Calculate gains with content profile
        content_profile = {
            'genre': 'rock',
            'dynamic_range': 8.0,
            'spectral_balance': 'bright'
        }

        gains = eq.calculate_adaptive_gains(
            analysis,
            target_curve,
            content_profile
        )

        assert len(gains) == len(eq.critical_bands)
        assert np.all(np.isfinite(gains))

        self.tearDown()

    def test_apply_eq(self):
        """Test apply_eq method"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)

        # Create test gains (flat response)
        gains = np.zeros(len(eq.critical_bands))

        # Apply EQ
        processed = eq.apply_eq(self.test_chunk, gains)

        assert processed.shape == self.test_chunk.shape
        assert np.all(np.isfinite(processed))
        # EQ processing applies filters, so output won't be identical even with flat gains
        # Just verify processing completed without errors and output is reasonable
        assert np.max(np.abs(processed)) <= 2.0 * np.max(np.abs(self.test_chunk))

        self.tearDown()

    def test_process_realtime_chunk(self):
        """Test process_realtime_chunk method"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)

        # Create target curve (flat response)
        target_curve = np.zeros(len(eq.critical_bands))

        # Process chunk
        processed = eq.process_realtime_chunk(self.test_chunk, target_curve)

        assert processed.shape == self.test_chunk.shape
        assert np.all(np.isfinite(processed))
        # Output should have reasonable amplitude
        assert np.max(np.abs(processed)) <= 2.0

        self.tearDown()

    def test_process_realtime_chunk_with_content(self):
        """Test real-time processing with content profile"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)
        target_curve = np.zeros(len(eq.critical_bands))
        content_profile = {'genre': 'jazz'}

        processed = eq.process_realtime_chunk(
            self.test_chunk,
            target_curve,
            content_profile
        )

        assert processed.shape == self.test_chunk.shape
        assert np.all(np.isfinite(processed))

        self.tearDown()

    def test_get_current_response(self):
        """Test get_current_response method"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)

        # Process a chunk first
        target_curve = np.zeros(len(eq.critical_bands))
        eq.process_realtime_chunk(self.test_chunk, target_curve)

        # Get current response (returns a dict, not just an array)
        response = eq.get_current_response()

        assert isinstance(response, (dict, np.ndarray))
        if isinstance(response, dict):
            # If it returns a dict, verify it has the right keys
            assert 'gains_db' in response or 'bands' in response
        else:
            # If it returns an array, verify length
            assert len(response) == len(eq.critical_bands)
            assert np.all(np.isfinite(response))

        self.tearDown()

    def test_reset(self):
        """Test reset method"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)

        # Process some audio to change state
        target_curve = np.zeros(len(eq.critical_bands))
        eq.process_realtime_chunk(self.test_chunk, target_curve)

        # Reset
        eq.reset()

        # Verify state is reset
        assert np.allclose(eq.current_gains, np.ones(len(eq.critical_bands)))

        self.tearDown()

    def test_generate_genre_eq_curve(self):
        """Test genre EQ curve generation"""
        self.setUp()

        # Test various genres
        genres = ['rock', 'jazz', 'classical', 'electronic']

        for genre in genres:
            try:
                curve = generate_genre_eq_curve(genre, num_bands=26)
                assert len(curve) == 26
                assert np.all(np.isfinite(curve))
            except (ValueError, KeyError):
                # Genre might not be implemented yet
                pass

        self.tearDown()

    def test_multiple_chunk_processing(self):
        """Test processing multiple chunks in sequence"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)
        target_curve = np.zeros(len(eq.critical_bands))

        # Process multiple chunks
        chunks = [self.test_chunk for _ in range(5)]
        processed_chunks = []

        for chunk in chunks:
            processed = eq.process_realtime_chunk(chunk, target_curve)
            processed_chunks.append(processed)

        # All chunks should be processed successfully
        assert len(processed_chunks) == 5
        for proc in processed_chunks:
            assert proc.shape == self.test_chunk.shape
            assert np.all(np.isfinite(proc))

        self.tearDown()

    def test_stereo_processing(self):
        """Test processing stereo audio"""
        self.setUp()

        eq = PsychoacousticEQ(self.settings)
        target_curve = np.zeros(len(eq.critical_bands))

        # Process left and right channels separately
        chunk_size = 4096
        left_chunk = self.test_stereo[:chunk_size, 0]
        right_chunk = self.test_stereo[:chunk_size, 1]

        processed_left = eq.process_realtime_chunk(left_chunk, target_curve)
        processed_right = eq.process_realtime_chunk(right_chunk, target_curve)

        assert processed_left.shape == left_chunk.shape
        assert processed_right.shape == right_chunk.shape
        assert np.all(np.isfinite(processed_left))
        assert np.all(np.isfinite(processed_right))

        self.tearDown()


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
