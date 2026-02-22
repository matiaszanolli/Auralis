"""
Regression test: parallel sub-bass processing dtype preservation (#2368, #2158)

Verifies that ParallelEQUtilities preserves dtype (float32) after sosfilt()
returns float64, and preserves output shape for mono and stereo audio.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import numpy as np
import pytest

from auralis.core.dsp.parallel_eq import ParallelEQUtilities


class TestParallelEQDtypePreservation:
    """Regression: sosfilt() returns float64 regardless of input dtype (#2158)."""

    @pytest.mark.parametrize("method,kwargs", [
        ("apply_low_shelf_boost", {"boost_db": 3.0, "freq_hz": 80.0}),
        ("apply_high_shelf_boost", {"boost_db": 2.5, "freq_hz": 10000.0}),
        ("apply_bandpass_boost", {"boost_db": 2.0, "low_hz": 200.0, "high_hz": 4000.0}),
    ])
    def test_float32_preserved_mono(self, method, kwargs):
        audio = np.random.randn(44100).astype(np.float32)
        result = getattr(ParallelEQUtilities, method)(audio, sample_rate=44100, **kwargs)
        assert result.dtype == np.float32, f"{method} returned {result.dtype}, expected float32"
        assert result.shape == audio.shape

    @pytest.mark.parametrize("method,kwargs", [
        ("apply_low_shelf_boost", {"boost_db": 3.0, "freq_hz": 80.0}),
        ("apply_high_shelf_boost", {"boost_db": 2.5, "freq_hz": 10000.0}),
        ("apply_bandpass_boost", {"boost_db": 2.0, "low_hz": 200.0, "high_hz": 4000.0}),
    ])
    def test_float32_preserved_stereo(self, method, kwargs):
        audio = np.random.randn(2, 44100).astype(np.float32)
        result = getattr(ParallelEQUtilities, method)(audio, sample_rate=44100, **kwargs)
        assert result.dtype == np.float32, f"{method} returned {result.dtype}, expected float32"
        assert result.shape == audio.shape

    def test_output_shape_unchanged(self):
        """Output must have identical shape to input (no sample count change)."""
        for shape in [(44100,), (2, 44100), (6, 44100)]:
            audio = np.random.randn(*shape).astype(np.float32)
            result = ParallelEQUtilities.apply_low_shelf_boost(
                audio, boost_db=2.0, freq_hz=100.0, sample_rate=44100
            )
            assert result.shape == shape, f"Shape mismatch: {result.shape} != {shape}"

    def test_zero_boost_identity(self):
        """0 dB boost should return audio nearly unchanged."""
        audio = np.random.randn(2, 44100).astype(np.float32)
        result = ParallelEQUtilities.apply_low_shelf_boost(
            audio, boost_db=0.0, freq_hz=100.0, sample_rate=44100
        )
        np.testing.assert_allclose(result, audio, atol=1e-6)
