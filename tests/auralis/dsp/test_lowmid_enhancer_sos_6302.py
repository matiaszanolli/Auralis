"""LowMidTransientEnhancer's filters are second-order sections, stable at every rate (#6302).

``signal.butter(4, [150/nyq, 1500/nyq], btype='band')`` returned (b, a) polynomials; with the 150 Hz edge at
0.0016 of Nyquist at 192 kHz the order-8 direct form is ill-conditioned (it was unstable from 176.4 kHz up).
"""

import numpy as np
import pytest
from scipy import signal

from auralis.dsp.dynamics.lowmid_transient_enhancer import LowMidTransientEnhancer


@pytest.mark.parametrize("sample_rate", [22050, 44100, 96000, 176400, 192000, 384000])
def test_the_band_filter_is_stable_and_passes_the_band_at_every_rate(sample_rate):
    enhancer = LowMidTransientEnhancer(sample_rate=sample_rate)

    freqs = np.array([75.0, 300.0, 700.0, 3000.0])
    _, response = signal.sosfreqz(enhancer.sos_low_mid, worN=freqs, fs=sample_rate)
    magnitude_db = 20 * np.log10(np.abs(response))

    assert np.isfinite(magnitude_db).all()
    assert magnitude_db[1] > -1.0 and magnitude_db[2] > -1.0   # the 150-1500 Hz band passes
    assert magnitude_db[0] < -2.0 and magnitude_db[3] < -10.0  # and the band edges reject


@pytest.mark.parametrize("sample_rate", [44100, 192000])
def test_enhancing_returns_finite_audio_of_the_same_shape(sample_rate):
    rng = np.random.default_rng(6302)
    audio = (rng.standard_normal((sample_rate // 2, 2)) * 0.1).astype(np.float32)

    out = LowMidTransientEnhancer(sample_rate=sample_rate).enhance_transients(audio, intensity=0.7)

    assert out.shape == audio.shape and np.isfinite(out).all()
