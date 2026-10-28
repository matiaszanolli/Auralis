"""The -50 LUFS silence floor is a ramp, not a step (#6108)

``_normalize_chunk_loudness`` left audio untouched at or below -50 LUFS and otherwise applied the
full (up to 24 dB) correction, so inputs 0.2 dB apart around the floor got gains ~22 dB apart.
The correction now fades in over ``SILENCE_KNEE_DB`` above the floor.
"""

import numpy as np
import pytest

from auralis.core.processing.continuous_dsp_ops import ContinuousDSPOpsMixin
from auralis.dsp.utils.adaptive import (
    SILENCE_FLOOR_LUFS,
    SILENCE_KNEE_DB,
    calculate_loudness_units,
)

SR = 44100
TARGET = -28.0


class _Cfg:
    internal_sample_rate = SR


@pytest.fixture
def ops() -> ContinuousDSPOpsMixin:
    ops = ContinuousDSPOpsMixin.__new__(ContinuousDSPOpsMixin)
    ops.config = _Cfg()
    return ops


def _noise_at(lufs: float) -> np.ndarray:
    """Stereo noise scaled so the meter reads *lufs*."""
    rng = np.random.default_rng(6108)
    audio = rng.standard_normal((SR * 3, 2)).astype(np.float32) * 0.01
    gain_db = lufs - calculate_loudness_units(audio, SR)
    return (audio * 10 ** (gain_db / 20)).astype(np.float32)


def _applied_gain_db(ops, audio: np.ndarray) -> float:
    out = ops._normalize_chunk_loudness(audio.copy(), TARGET)
    return float(20 * np.log10(np.max(np.abs(out)) / np.max(np.abs(audio))))


def test_gain_is_continuous_across_the_floor(ops):
    just_below = _applied_gain_db(ops, _noise_at(SILENCE_FLOOR_LUFS - 0.1))
    just_above = _applied_gain_db(ops, _noise_at(SILENCE_FLOOR_LUFS + 0.1))

    assert just_below == pytest.approx(0.0, abs=1e-3)
    assert abs(just_above - just_below) < 0.5  # was ~22 dB


def test_gain_grows_monotonically_through_the_knee(ops):
    gains = [
        _applied_gain_db(ops, _noise_at(SILENCE_FLOOR_LUFS + frac * SILENCE_KNEE_DB))
        for frac in (0.1, 0.4, 0.7, 1.0)
    ]

    assert gains == sorted(gains)
    assert gains[-1] > 10.0  # full correction (target - input is ~17 dB) above the knee


def test_audio_at_or_below_the_floor_is_untouched(ops):
    audio = _noise_at(SILENCE_FLOOR_LUFS - 5.0)

    np.testing.assert_array_equal(ops._normalize_chunk_loudness(audio.copy(), TARGET), audio)
