"""The fingerprint must not change with playback level or with silent seconds.

#6112: `spectral_flatness` (and `harmonic_ratio = 1 - flatness`) came from one
whole-track FFT whose bins were dropped below an ABSOLUTE floor, so the same
audio read 0.08 at -24 dBFS and 0.96 at -64 dBFS. It is now per STFT frame,
with a floor relative to each frame, and mapped from dB onto 0-1.

#6113: the three variation dimensions scored digitally silent seconds, so a
1 s gap in steady material read as wildly dynamic (loudness_variation_std 0.05
-> 12.7 dB). Silent frames are left to `silence_ratio` now.

Both change stored values, so the algorithm version moved to 16.
"""

import numpy as np
import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.analysis.fingerprint.rust_fingerprint import compute_fingerprint_schema
from auralis.analysis.fingerprint.schema import DIMENSION_SCHEMA

SAMPLE_RATE = 22050
VARIATION_KEYS = ("loudness_variation_std", "dynamic_range_variation", "peak_consistency")


def _fingerprint(mono: np.ndarray) -> dict[str, float]:
    stereo = np.column_stack([mono, mono]).astype(np.float32)
    return compute_fingerprint_schema(np.ascontiguousarray(stereo.ravel()), SAMPLE_RATE, 2)


def _steady_noise(seconds: int) -> np.ndarray:
    return (0.1 * np.random.default_rng(3).standard_normal(SAMPLE_RATE * seconds)).astype(np.float32)


def _chord_over_noise(seconds: int) -> np.ndarray:
    t = np.arange(SAMPLE_RATE * seconds) / SAMPLE_RATE
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 277.2, 329.6)) * 0.15
    return (chord + 0.01 * np.random.default_rng(4).standard_normal(t.size)).astype(np.float32)


@pytest.fixture(scope="module")
def chord_fingerprint() -> dict[str, float]:
    return _fingerprint(_chord_over_noise(30))


@pytest.mark.parametrize("gain_db", [-20.0, -40.0])
def test_flatness_and_harmonic_ratio_do_not_depend_on_level(chord_fingerprint, gain_db):
    quieter = _fingerprint(_chord_over_noise(30) * np.float32(10 ** (gain_db / 20)))
    for key in ("spectral_flatness", "harmonic_ratio"):
        assert quieter[key] == pytest.approx(chord_fingerprint[key], abs=0.02), key


def test_noise_reads_flatter_than_a_chord(chord_fingerprint):
    noise = _fingerprint(_steady_noise(30))
    assert noise["spectral_flatness"] > 0.85
    assert chord_fingerprint["spectral_flatness"] < 0.5
    assert noise["harmonic_ratio"] < chord_fingerprint["harmonic_ratio"]


@pytest.mark.parametrize("gap_s", [1, 3, 10])
def test_silent_seconds_do_not_inflate_the_variation_dimensions(gap_s):
    steady = _steady_noise(60)
    reference = _fingerprint(steady)
    split = 20 * SAMPLE_RATE
    gapped = _fingerprint(np.concatenate([steady[:split], np.zeros(gap_s * SAMPLE_RATE, np.float32), steady[split:]]))
    for key in VARIATION_KEYS:
        assert gapped[key] == pytest.approx(reference[key], rel=0.1, abs=0.02), key


def test_loudness_variation_stays_in_its_schema_range():
    # Alternating loud and quiet (but audible) seconds: as variable as audio gets.
    seconds = [_steady_noise(1) * (1.0 if i % 2 else 0.012) for i in range(30)]
    fingerprint = _fingerprint(np.concatenate(seconds))
    _, low, high = DIMENSION_SCHEMA["loudness_variation_std"]
    assert low <= fingerprint["loudness_variation_std"] <= high


def test_stored_v15_rows_are_recomputed():
    assert FINGERPRINT_ALGORITHM_VERSION >= 16
