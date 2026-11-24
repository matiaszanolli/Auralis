"""
Long inputs fingerprint as precisely as short ones (#6362, #6363)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since v13 the engine analyses whole tracks (up to ~20M samples), but centroid,
rolloff, RMS and the stereo reductions kept f32 running sums, and centroid/rolloff
came from one whole-track f32 FFT. The error grew with duration: 900 s of pink
noise read its rolloff 50% low, `lufs` 0.1-0.2 dB low and `phase_correlation`
0.9026 against 0.8823. Every spectral dimension now reads one f64 frame spectrum
(the band shares' frames), and the time-domain sums are f64.

The reference below is numpy in f64 with the engine's definitions: 65536-sample
frames (a tail under half a frame is dropped), a periodic Hann window over each
frame, power summed over frames, 85% rolloff, ``20*log10(rms) - 0.7`` loudness on
the mono mix, and the Pearson correlation of the two channels.
"""

import numpy as np
import pytest

auralis_dsp = pytest.importorskip("auralis_dsp")

SR = 22050                      # the fingerprint's analysis rate
SECONDS = 480                   # issue acceptance: at least 8 minutes
FRAME = 65536


def _pink(n: int, rng: np.random.Generator) -> np.ndarray:
    spectrum = np.fft.rfft(rng.standard_normal(n))
    k = np.arange(len(spectrum), dtype=np.float64)
    k[0] = 1.0
    x = np.fft.irfft(spectrum / np.sqrt(k), n)
    return x / np.abs(x).max() * 0.5


@pytest.fixture(scope="module")
def stereo():
    rng = np.random.default_rng(6362)
    n = SR * SECONDS
    common, a, b = _pink(n, rng), _pink(n, rng), _pink(n, rng)
    left = (0.8 * common + 0.3 * a).astype(np.float32)
    right = (0.8 * common + 0.3 * b).astype(np.float32)
    interleaved = np.empty(2 * n, dtype=np.float32)
    interleaved[0::2], interleaved[1::2] = left, right
    return left, right, auralis_dsp.compute_fingerprint(interleaved, SR, 2)


def _reference_spectrum(mono: np.ndarray) -> np.ndarray:
    power = np.zeros(FRAME // 2 + 1)
    for start in range(0, len(mono), FRAME):
        frame = mono[start:start + FRAME].astype(np.float64)
        if start and len(frame) < FRAME // 2:
            break
        window = 0.5 * (1.0 - np.cos(2.0 * np.pi * np.arange(len(frame)) / len(frame)))
        power += np.abs(np.fft.rfft(frame * window, FRAME)) ** 2
    return power


def _mono(left, right):
    return ((left + right) * np.float32(0.5)).astype(np.float32)


def test_centroid_and_rolloff_match_the_f64_reference(stereo):
    left, right, fp = stereo
    power = _reference_spectrum(_mono(left, right))
    freqs = np.arange(len(power)) * SR / FRAME
    centroid = float(np.sum(power * freqs) / np.sum(power))
    rolloff = float(freqs[np.searchsorted(np.cumsum(power), 0.85 * power.sum())])

    assert fp["spectral_centroid"] == pytest.approx(centroid, rel=0.02)
    assert fp["spectral_rolloff"] == pytest.approx(rolloff, rel=0.02)


def test_loudness_and_crest_match_the_f64_reference(stereo):
    left, right, fp = stereo
    mono = _mono(left, right).astype(np.float64)
    rms = np.sqrt(np.mean(mono ** 2))
    assert fp["lufs"] == pytest.approx(20 * np.log10(rms) - 0.7, abs=0.01)
    assert fp["crest_db"] == pytest.approx(20 * np.log10(np.max(np.abs(mono)) / rms), abs=0.01)


def test_phase_correlation_matches_the_f64_reference(stereo):
    left, right, fp = stereo
    truth = float(np.corrcoef(left.astype(np.float64), right.astype(np.float64))[0, 1])
    assert fp["phase_correlation"] == pytest.approx(truth, abs=0.002)


def test_a_long_input_reads_like_its_own_first_minute(stereo):
    """The drift itself: a minute repeated 8 times must read exactly like that minute.

    Tiled from a whole number of frames, so the long input is the short one's frames
    repeated and only accumulation error could tell them apart. (Not the fixture's
    own 8 minutes: one pink-noise realisation is not statistically identical over its
    first minute and its whole length, and seams inside a frame change its spectrum.)
    """
    left, right, _ = stereo
    n = FRAME * 20                 # ~59 s

    def fingerprint(repeats: int) -> dict:
        audio = np.empty(2 * n * repeats, dtype=np.float32)
        audio[0::2], audio[1::2] = np.tile(left[:n], repeats), np.tile(right[:n], repeats)
        return auralis_dsp.compute_fingerprint(audio, SR, 2)

    short, long = fingerprint(1), fingerprint(8)
    for key in ("spectral_centroid", "spectral_rolloff", "lufs", "crest_db", "phase_correlation"):
        assert long[key] == pytest.approx(short[key], rel=1e-4, abs=1e-4), key
