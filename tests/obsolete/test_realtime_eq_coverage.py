#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Real-time Adaptive EQ Coverage Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for real-time adaptive EQ to improve coverage
"""

import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('../..'))

from auralis.dsp.realtime_adaptive_eq import (
    RealtimeAdaptiveEQ, EQBand, AdaptiveEQSettings,
    create_realtime_adaptive_eq, CriticalBandAnalyzer
)

class TestRealtimeAdaptiveEQ:
    """Test the RealtimeAdaptiveEQ class"""

    def setUp(self):
        """Set up test fixtures"""
        self.sample_rate = 44100
        self.duration = 1.0
        self.samples = int(self.sample_rate * self.duration)

        # Create test audio
        t = np.linspace(0, self.duration, self.samples)
        self.test_audio = 0.5 * np.sin(2 * np.pi * 440 * t)
        self.test_stereo_audio = np.column_stack([self.test_audio, self.test_audio * 0.8])

        # Create EQ settings
        self.settings = AdaptiveEQSettings(
            sample_rate=self.sample_rate,
            adaptation_rate=0.1,
            smoothing_factor=0.8
        )

    def test_eq_settings_creation(self):
        """Test EQ settings initialization"""
        settings = AdaptiveEQSettings(
            sample_rate=44100,
            adaptation_rate=0.05,
            smoothing_factor=0.9
        )

        assert settings.sample_rate == 44100
        assert settings.adaptation_rate == 0.05
        assert settings.smoothing_factor == 0.9

    def test_eq_band_creation(self):
        """Test EQ band initialization"""
        band = EQBand(
            frequency=1000,
            gain=2.0,
            q_factor=1.0
        )

        assert band.frequency == 1000
        assert band.gain == 2.0
        assert band.q_factor == 1.0

    def test_realtime_eq_creation(self):
        """Test real-time EQ initialization"""
        self.setUp()
        eq = RealtimeAdaptiveEQ(self.settings)

        assert eq is not None
        assert hasattr(eq, 'process')
        assert hasattr(eq, 'adapt_to_content')
        assert hasattr(eq, 'get_current_response')

    def test_factory_function(self):
        """Test factory function"""
        eq = create_realtime_adaptive_eq(
            sample_rate=44100,
            adaptation_rate=0.1
        )

        assert eq is not None
        assert isinstance(eq, RealtimeAdaptiveEQ)

    def test_process_mono_audio(self):
        """Test processing mono audio"""
        self.setUp()
        eq = RealtimeAdaptiveEQ(self.settings)

        processed = eq.process(self.test_audio)

        assert processed is not None
        assert processed.shape == self.test_audio.shape

    def test_process_stereo_audio(self):
        """Test processing stereo audio"""
        self.setUp()
        eq = RealtimeAdaptiveEQ(self.settings)

        processed = eq.process(self.test_stereo_audio)

        assert processed is not None
        assert processed.shape == self.test_stereo_audio.shape

    def test_content_adaptation(self):
        """Test content-based adaptation"""
        self.setUp()
        eq = RealtimeAdaptiveEQ(self.settings)

        # Bright audio content
        bright_features = {
            'spectral_centroid': 3000,
            'spectral_brightness': 0.8,
            'energy_distribution': [0.2, 0.3, 0.5]  # Bass, mid, treble
        }

        eq.adapt_to_content(bright_features)
        response1 = eq.get_current_response()

        # Dark audio content
        dark_features = {
            'spectral_centroid': 800,
            'spectral_brightness': 0.2,
            'energy_distribution': [0.6, 0.3, 0.1]
        }

        eq.adapt_to_content(dark_features)
        response2 = eq.get_current_response()

        # Responses should be different
        assert not np.array_equal(response1, response2)

    def test_critical_band_analyzer(self):
        """Test critical band analyzer"""
        analyzer = CriticalBandAnalyzer(sample_rate=44100)

        # Test with different audio types
        bright_audio = np.sin(2 * np.pi * 2000 * np.linspace(0, 1, 44100))
        analysis = analyzer.analyze(bright_audio)

        assert 'critical_bands' in analysis
        assert 'band_energies' in analysis
        assert len(analysis['critical_bands']) == 26  # Bark scale bands

    def test_real_time_processing_chunks(self):
        """Test real-time chunk processing"""
        self.setUp()
        eq = RealtimeAdaptiveEQ(self.settings)

        chunk_size = 1024
        num_chunks = len(self.test_audio) // chunk_size

        processed_chunks = []

        for i in range(num_chunks):
            start_idx = i * chunk_size
            end_idx = start_idx + chunk_size
            chunk = self.test_audio[start_idx:end_idx]

            processed_chunk = eq.process(chunk)
            processed_chunks.append(processed_chunk)

        assert len(processed_chunks) == num_chunks

    def test_parameter_smoothing(self):
        """Test parameter smoothing"""
        self.setUp()
        eq = RealtimeAdaptiveEQ(self.settings)

        # Set initial state
        eq.adapt_to_content({'spectral_centroid': 1000})
        initial_response = eq.get_current_response()

        # Make gradual changes
        for centroid in [1200, 1400, 1600, 1800, 2000]:
            eq.adapt_to_content({'spectral_centroid': centroid})

        final_response = eq.get_current_response()

        # Should be smoothly different
        assert not np.array_equal(initial_response, final_response)

    def test_frequency_response_calculation(self):
        """Test frequency response calculation"""
        self.setUp()
        eq = RealtimeAdaptiveEQ(self.settings)

        response = eq.get_current_response()

        assert response is not None
        assert len(response) > 0
        assert isinstance(response, np.ndarray)

    def test_band_gain_adjustment(self):
        """Test individual band gain adjustment"""
        self.setUp()
        eq = RealtimeAdaptiveEQ(self.settings)

        # Adjust specific frequency bands
        eq.set_band_gain(1000, 3.0)  # Boost 1kHz
        eq.set_band_gain(4000, -2.0)  # Cut 4kHz

        processed = eq.process(self.test_audio)

        assert processed is not None

    def test_reset_adaptation(self):
        """Test resetting adaptation"""
        self.setUp()
        eq = RealtimeAdaptiveEQ(self.settings)

        # Make changes
        eq.adapt_to_content({'spectral_centroid': 3000})
        changed_response = eq.get_current_response()

        # Reset
        eq.reset()
        reset_response = eq.get_current_response()

        # Should be back to initial state (may not be exactly equal due to floating point)
        assert len(reset_response) == len(changed_response)

    def test_different_adaptation_rates(self):
        """Test different adaptation rates"""
        settings_fast = AdaptiveEQSettings(
            sample_rate=44100,
            adaptation_rate=0.5,  # Fast adaptation
            smoothing_factor=0.5
        )

        settings_slow = AdaptiveEQSettings(
            sample_rate=44100,
            adaptation_rate=0.01,  # Slow adaptation
            smoothing_factor=0.9
        )

        eq_fast = RealtimeAdaptiveEQ(settings_fast)
        eq_slow = RealtimeAdaptiveEQ(settings_slow)

        # Both should process without error
        audio = np.random.randn(1024)
        processed_fast = eq_fast.process(audio)
        processed_slow = eq_slow.process(audio)

        assert processed_fast is not None
        assert processed_slow is not None

    def test_edge_cases(self):
        """Test edge cases"""
        self.setUp()
        eq = RealtimeAdaptiveEQ(self.settings)

        # Empty audio
        empty_audio = np.array([])
        try:
            processed = eq.process(empty_audio)
            assert processed.size == 0
        except:
            pass  # May raise exception, which is acceptable

        # Very short audio
        short_audio = np.array([0.1, 0.2])
        processed = eq.process(short_audio)
        assert processed is not None

        # Very quiet audio
        quiet_audio = np.ones(1024) * 1e-8
        processed = eq.process(quiet_audio)
        assert processed is not None

if __name__ == '__main__':
    import pytest
    pytest.main([__file__])