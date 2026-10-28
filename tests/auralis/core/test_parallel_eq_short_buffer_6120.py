"""ParallelEQUtilities adds nothing to a buffer too short to filter (#6120).

The three boosts extract a band and add `band * (gain - 1)` back. For a buffer no
longer than scipy's padlen the extraction fell back to passthrough, so the "band"
was the WHOLE signal and the parallel add became a broadband gain of +boost_db on
the chunk loop's tiny final chunk. A band that cannot be extracted holds no
energy, so the buffer must come back unchanged.
"""

import numpy as np
import pytest

from auralis.core.dsp.parallel_eq import ParallelEQUtilities as EQ

SR = 44100


def _audio(n: int, dtype=np.float32) -> np.ndarray:
    return (0.3 * np.random.default_rng(n).standard_normal((2, n))).astype(dtype)


# order-2 low/high shelves are one section (padlen 9); the bandpass has two (padlen 15).
SHELF_TOO_SHORT = [1, 2, 5, 9]
BANDPASS_TOO_SHORT = [1, 2, 5, 9, 12, 15]


@pytest.mark.parametrize("n", SHELF_TOO_SHORT)
def test_low_shelf_leaves_a_too_short_buffer_unchanged(n):
    audio = _audio(n)
    out = EQ.apply_low_shelf_boost(audio, boost_db=6.0, freq_hz=120.0, sample_rate=SR)
    np.testing.assert_array_equal(out, audio)


@pytest.mark.parametrize("n", SHELF_TOO_SHORT)
def test_high_shelf_leaves_a_too_short_buffer_unchanged(n):
    audio = _audio(n)
    out = EQ.apply_high_shelf_boost(audio, boost_db=6.0, freq_hz=8000.0, sample_rate=SR)
    np.testing.assert_array_equal(out, audio)


@pytest.mark.parametrize("n", BANDPASS_TOO_SHORT)
def test_bandpass_leaves_a_too_short_buffer_unchanged(n):
    audio = _audio(n)
    out = EQ.apply_bandpass_boost(audio, boost_db=6.0, low_hz=200.0, high_hz=2000.0, sample_rate=SR)
    np.testing.assert_array_equal(out, audio)


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_dtype_and_shape_survive_a_short_buffer(dtype):
    audio = _audio(5, dtype)
    out = EQ.apply_low_shelf_boost(audio, boost_db=6.0, freq_hz=120.0, sample_rate=SR)
    assert out.dtype == audio.dtype and out.shape == audio.shape


def test_a_long_enough_buffer_still_boosts():
    """The fix must not turn the stage off: a real buffer still gets its band."""
    t = np.arange(SR) / SR
    audio = np.stack([0.2 * np.sin(2 * np.pi * 60 * t)] * 2).astype(np.float32)

    out = EQ.apply_low_shelf_boost(audio, boost_db=6.0, freq_hz=120.0, sample_rate=SR)

    assert np.max(np.abs(out)) > np.max(np.abs(audio)) * 1.5
