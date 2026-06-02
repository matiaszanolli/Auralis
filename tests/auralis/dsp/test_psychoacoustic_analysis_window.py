"""
Regression test: PsychoacousticEQ.analyze_spectrum windows the analysis FFT (#4101)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The analysis FFT was rectangular (#3663), so its -13 dB first sidelobe leaked
bass energy into adjacent critical bands and biased the masking calculator. The
analysis path now applies a Hann window with coherent-gain compensation:
leakage drops while the absolute magnitude scale stays equal to the un-windowed
path (no #3428 global-offset regression). The filter-application path
(apply_eq_gains) stays un-windowed.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import numpy as np
from scipy.fft import fft

from auralis.dsp.eq.psychoacoustic_eq import EQSettings, PsychoacousticEQ


def _eq() -> PsychoacousticEQ:
    return PsychoacousticEQ(EQSettings(sample_rate=44100, fft_size=4096))


def _tone(freq: float, n: int, sr: int = 44100) -> np.ndarray:
    t = np.arange(n) / sr
    return (0.8 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_window_reduces_sidelobe_leakage_vs_rectangular():
    """Windowed analysis leaks far less into bins away from a 60 Hz tone."""
    eq = _eq()
    fft_size = eq.fft_size
    sr = eq.sample_rate
    audio = _tone(60.0, fft_size, sr)

    result = eq.analyze_spectrum(audio)
    windowed_mag = np.abs(result["spectrum"])[: fft_size // 2 + 1]

    # Rectangular baseline (what #3663 produced).
    rect_mag = np.abs(fft(audio[:fft_size]))[: fft_size // 2 + 1]

    bin_hz = sr / fft_size
    peak_bin = int(round(60.0 / bin_hz))
    # Look ~3-4 critical bands above 60 Hz (roughly 250-400 Hz region).
    far_lo = int(round(250.0 / bin_hz))
    far_hi = int(round(450.0 / bin_hz))

    windowed_leak = float(np.mean(windowed_mag[far_lo:far_hi]))
    rect_leak = float(np.mean(rect_mag[far_lo:far_hi]))

    assert windowed_leak < rect_leak * 0.5, (
        f"window should cut bass leakage: windowed={windowed_leak:.4g} "
        f"vs rectangular={rect_leak:.4g}"
    )
    # The tone peak itself is still clearly present.
    assert windowed_mag[peak_bin] > windowed_leak * 10


def test_coherent_gain_preserved_no_global_offset():
    """The tone's peak magnitude matches the un-windowed scale (no #3428 offset)."""
    eq = _eq()
    fft_size = eq.fft_size
    sr = eq.sample_rate
    audio = _tone(1000.0, fft_size, sr)  # bin-centered-ish, away from edges

    windowed_peak = np.max(np.abs(eq.analyze_spectrum(audio)["spectrum"]))
    rect_peak = np.max(np.abs(fft(audio[:fft_size])))

    # Coherent-gain compensation keeps the peak within ~1 dB of rectangular,
    # i.e. no systematic magnitude inflation/deflation.
    ratio_db = 20 * np.log10(windowed_peak / rect_peak)
    assert abs(ratio_db) < 1.0, f"unexpected global magnitude offset: {ratio_db:+.2f} dB"


def test_output_shape_and_finiteness():
    eq = _eq()
    audio = _tone(440.0, eq.fft_size, eq.sample_rate)
    result = eq.analyze_spectrum(audio)
    assert np.all(np.isfinite(result["magnitude_db"]))
    assert np.all(np.isfinite(result["band_energies"]))
    assert result["spectrum"].shape[0] == eq.fft_size
