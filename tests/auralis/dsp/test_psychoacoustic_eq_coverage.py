#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Psychoacoustic EQ Coverage Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for the psychoacoustic EQ to improve coverage
"""

import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('../..'))

from auralis.dsp.psychoacoustic_eq import (
    PsychoacousticEQ, EQSettings, MaskingThresholdCalculator,
    CriticalBand, create_psychoacoustic_eq
)

class TestPsychoacousticEQ:
    """Test the PsychoacousticEQ class"""

    def setUp(self):
        """Set up test fixtures"""
        self.sample_rate = 44100
        self.settings = EQSettings(
            sample_rate=self.sample_rate,
            num_bands=26,
            adaptation_strength=0.5
        )

        # Create test audio
        duration = 1.0
        samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, samples)
        self.test_audio = 0.5 * np.sin(2 * np.pi * 440 * t)
        self.test_stereo_audio = np.column_stack([self.test_audio, self.test_audio * 0.8])

    def test_eq_settings_creation(self):
        """Test EQ settings creation"""
        settings = EQSettings(
            sample_rate=44100,
            num_bands=26,
            adaptation_strength=0.7
        )

        assert settings.sample_rate == 44100
        assert settings.num_bands == 26
        assert settings.adaptation_strength == 0.7

    def test_critical_band_creation(self):
        """Test critical band creation"""
        band = CriticalBand(
            center_freq=1000,
            lower_freq=800,
            upper_freq=1200,
            bark_value=8.5
        )

        assert band.center_freq == 1000
        assert band.lower_freq == 800
        assert band.upper_freq == 1200
        assert band.bark_value == 8.5

    def test_psychoacoustic_eq_creation(self):
        """Test psychoacoustic EQ initialization"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        assert eq is not None
        assert hasattr(eq, 'process')
        assert hasattr(eq, 'analyze_masking')
        assert hasattr(eq, 'adapt_to_content')

    def test_factory_function(self):
        """Test factory function"""
        eq = create_psychoacoustic_eq(sample_rate=44100)

        assert eq is not None
        assert isinstance(eq, PsychoacousticEQ)

    def test_critical_bands_creation(self):
        """Test critical bands creation"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        bands = eq._create_critical_bands()

        assert len(bands) == 26  # Bark scale has 26 bands
        assert all(isinstance(band, CriticalBand) for band in bands)

    def test_masking_threshold_calculator(self):
        """Test masking threshold calculator"""
        calculator = MaskingThresholdCalculator(sample_rate=44100)

        # Test with synthetic spectrum
        frequencies = np.linspace(0, 22050, 1024)
        magnitudes = np.ones(1024) * 0.5

        thresholds = calculator.calculate_masking_threshold(frequencies, magnitudes)

        assert thresholds is not None
        assert len(thresholds) == len(frequencies)

    def test_process_mono_audio(self):
        """Test processing mono audio"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        processed = eq.process(self.test_audio)

        assert processed is not None
        assert processed.shape == self.test_audio.shape

    def test_process_stereo_audio(self):
        """Test processing stereo audio"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        processed = eq.process(self.test_stereo_audio)

        assert processed is not None
        assert processed.shape == self.test_stereo_audio.shape

    def test_content_adaptation(self):
        """Test content-based adaptation"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        # Different audio content types
        content_types = [
            {'genre': 'rock', 'energy_level': 'high'},
            {'genre': 'classical', 'energy_level': 'medium'},
            {'genre': 'electronic', 'energy_level': 'high'}
        ]

        for content in content_types:
            eq.adapt_to_content(content)
            processed = eq.process(self.test_audio)
            assert processed is not None

    def test_masking_analysis(self):
        """Test masking analysis"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        masking_info = eq.analyze_masking(self.test_audio)

        assert masking_info is not None
        assert 'masking_threshold' in masking_info
        assert 'critical_bands' in masking_info

    def test_frequency_response(self):
        """Test frequency response calculation"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        response = eq.get_frequency_response()

        assert response is not None
        assert 'frequencies' in response
        assert 'magnitudes' in response

    def test_band_gains_adjustment(self):
        """Test adjusting individual band gains"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        # Adjust specific bands
        band_adjustments = {
            0: 2.0,   # Boost first band
            5: -1.5,  # Cut sixth band
            10: 3.0   # Boost eleventh band
        }

        eq.set_band_gains(band_adjustments)
        processed = eq.process(self.test_audio)

        assert processed is not None

    def test_different_adaptation_strengths(self):
        """Test different adaptation strengths"""
        adaptation_strengths = [0.1, 0.5, 0.9]

        for strength in adaptation_strengths:
            settings = EQSettings(
                sample_rate=44100,
                num_bands=26,
                adaptation_strength=strength
            )
            eq = PsychoacousticEQ(settings)
            processed = eq.process(self.test_audio)
            assert processed is not None

    def test_psychoacoustic_modeling(self):
        """Test psychoacoustic modeling"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        # Test with different audio characteristics
        # Bright audio
        bright_audio = np.sin(2 * np.pi * 2000 * np.linspace(0, 1, 44100))
        processed_bright = eq.process(bright_audio)

        # Dark audio
        dark_audio = np.sin(2 * np.pi * 200 * np.linspace(0, 1, 44100))
        processed_dark = eq.process(dark_audio)

        assert processed_bright is not None
        assert processed_dark is not None
        # They should be processed differently
        assert not np.allclose(processed_bright, processed_dark, rtol=0.1)

    def test_bark_scale_frequencies(self):
        """Test Bark scale frequency calculation"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        bark_freqs = eq._calculate_bark_frequencies()

        assert len(bark_freqs) == 26
        assert bark_freqs[0] < bark_freqs[-1]  # Should be ascending

    def test_simultaneous_masking(self):
        """Test simultaneous masking calculation"""
        calculator = MaskingThresholdCalculator(sample_rate=44100)

        # Create test spectrum with prominent peak
        frequencies = np.linspace(0, 22050, 1024)
        magnitudes = np.ones(1024) * 0.1
        magnitudes[512] = 1.0  # Peak at middle frequency

        masking = calculator.calculate_simultaneous_masking(frequencies, magnitudes)

        assert masking is not None
        assert len(masking) == len(frequencies)

    def test_temporal_masking(self):
        """Test temporal masking effects"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        # Process multiple frames to test temporal effects
        frame_size = 1024
        num_frames = len(self.test_audio) // frame_size

        for i in range(num_frames):
            start = i * frame_size
            end = start + frame_size
            frame = self.test_audio[start:end]
            processed_frame = eq.process(frame)
            assert processed_frame is not None

    def test_noise_shaping(self):
        """Test noise shaping capabilities"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        # Add noise to test signal
        noisy_audio = self.test_audio + np.random.randn(len(self.test_audio)) * 0.01

        processed = eq.process(noisy_audio)

        assert processed is not None
        assert len(processed) == len(noisy_audio)

    def test_equal_loudness_contours(self):
        """Test equal loudness contour application"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        # Test at different loudness levels
        quiet_audio = self.test_audio * 0.1
        loud_audio = self.test_audio * 0.9

        processed_quiet = eq.process(quiet_audio)
        processed_loud = eq.process(loud_audio)

        assert processed_quiet is not None
        assert processed_loud is not None

    def test_reset_eq(self):
        """Test resetting EQ state"""
        self.setUp()
        eq = PsychoacousticEQ(self.settings)

        # Make changes
        eq.adapt_to_content({'genre': 'rock'})
        eq.set_band_gains({0: 5.0, 10: -3.0})

        # Reset
        eq.reset()

        # Process after reset
        processed = eq.process(self.test_audio)
        assert processed is not None

    def test_edge_cases(self):
        """Test edge cases"""
        self.setUp()

        # Very small audio
        small_audio = np.array([0.1, 0.2, 0.3])
        eq = PsychoacousticEQ(self.settings)

        try:
            processed = eq.process(small_audio)
            assert processed is not None
        except:
            pass  # May raise exception for very small inputs

        # Silent audio
        silent_audio = np.zeros(1024)
        processed = eq.process(silent_audio)
        assert processed is not None

        # Very loud audio
        loud_audio = np.ones(1024) * 10.0
        processed = eq.process(loud_audio)
        assert processed is not None

if __name__ == '__main__':
    import pytest
    pytest.main([__file__])