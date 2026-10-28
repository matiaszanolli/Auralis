"""A mono source is measured as the dual-mono stereo it is rendered as (#6138).

BS.1770 sums channel power, so the lone channel of a mono file read 3 LU below
the same signal on two channels, although the chunk loop renders it as
dual-mono. The loudness maximizer then pushed mono sources 3 LU harder.
"""

import numpy as np
import pytest

from auralis.core.mastering_prepare import measure_window_loudness

SR = 44100


def _tone(seconds=6.0):
    t = np.arange(int(SR * seconds)) / SR
    return (0.2 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


def test_mono_matches_the_same_signal_as_dual_mono_stereo():
    mono = _tone()
    stereo = np.stack([mono, mono], axis=1)

    mono_lufs, _ = measure_window_loudness(mono, SR)
    stereo_lufs, _ = measure_window_loudness(stereo, SR)

    assert mono_lufs is not None and stereo_lufs is not None
    assert mono_lufs == pytest.approx(stereo_lufs, abs=0.01)


def test_single_column_window_is_treated_like_mono():
    mono = _tone()

    column_lufs, _ = measure_window_loudness(mono[:, None], SR)
    flat_lufs, _ = measure_window_loudness(mono, SR)

    assert column_lufs == pytest.approx(flat_lufs, abs=0.01)


def test_stereo_is_not_double_counted():
    left, right = _tone(), 0.5 * _tone()
    lufs, _ = measure_window_loudness(np.stack([left, right], axis=1), SR)
    as_mono, _ = measure_window_loudness(left, SR)

    assert lufs is not None and as_mono is not None
    assert lufs < as_mono  # quieter right channel: below dual-mono of the louder one
