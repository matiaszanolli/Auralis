"""
#4622: sample_rate is required (no default) on module-level DSP helpers,
converting a silent 44.1kHz-fallback hazard into a compile/type-time error.

This test proves the parameter is actually load-bearing — not just present —
by showing a fixed FFT-bin-domain signal produces a different Hz-domain
result depending on which sample_rate is passed. If any of these functions
had ignored the argument (like the historical unused `sample_rate` on
`calculate_loudness_units`), the outputs would be identical and this test
would catch that regression.
"""

from __future__ import annotations

import numpy as np

from auralis.dsp.utils.spectral import spectral_centroid, spectral_rolloff


def test_spectral_centroid_scales_with_sample_rate():
    """Same bin index maps to a different Hz value at a different rate."""
    audio = np.zeros(8192, dtype=np.float32)
    audio[1000] = 1.0  # an impulse — its FFT energy sits at fixed bin indices

    centroid_44k = spectral_centroid(audio, 44100)
    centroid_48k = spectral_centroid(audio, 48000)

    assert centroid_44k != centroid_48k
    # Bin->Hz scaling is linear in sample_rate, so the ratio should track it.
    assert centroid_48k / centroid_44k > 1.0


def test_spectral_rolloff_scales_with_sample_rate():
    """Same digital signal (fixed bin content), interpreted at two rates.

    Using a tone built from a real-world Hz value at each rate (e.g. 1000Hz
    at both 44.1k and 48k) would defeat this test — the physical content
    differs too, so identical rolloff wouldn't prove the function ignores
    sample_rate. An impulse's FFT energy sits at fixed bin indices
    regardless of rate, so only the bin->Hz mapping the function computes
    from sample_rate can make the two outputs differ.
    """
    audio = np.zeros(8192, dtype=np.float32)
    audio[1000] = 1.0

    rolloff_44k = spectral_rolloff(audio, 44100)
    rolloff_48k = spectral_rolloff(audio, 48000)

    assert rolloff_44k != rolloff_48k
