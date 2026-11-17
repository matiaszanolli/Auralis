"""A hot source's master is not attenuated by an input-peak-keyed guard (#6320).

apply_true_peak_guard multiplied every chunk by -0.5 dBFS / (input peak *
4x overshoot) whenever that was below 1, so any input peaking above ~-0.77 dBFS
lost up to 0.76 dB although the two-pass correction (#5694) already measures
the final signal and holds the -0.5 dBTP ceiling. A peak-0.999 input mastered
0.8 dB quieter than a peak-0.6 copy of the same music.
"""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from scipy.signal import resample_poly

from tests.auralis.core.test_offline_file_gain_postchain_5694 import SR, _make_pipeline, _music_like


def _master(tmp_path: Path, input_peak: float) -> np.ndarray:
    src = tmp_path / f"in_{input_peak}.wav"
    dst = tmp_path / f"out_{input_peak}.wav"
    sf.write(str(src), _music_like(peak=input_peak), SR, subtype='FLOAT')
    _make_pipeline().master_file(input_path=str(src), output_path=str(dst), intensity=1.0, verbose=False)
    written, _ = sf.read(str(dst), dtype='float64')
    return written


def _rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(x ** 2))))


def _true_peak_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.max(np.abs(resample_poly(x, 4, 1, axis=0)))))


@pytest.mark.parametrize("hot_peak", [0.97, 0.999])
def test_hot_input_masters_as_loud_as_a_moderate_copy(tmp_path, hot_peak):
    moderate = _master(tmp_path, 0.6)
    hot = _master(tmp_path, hot_peak)

    # The guard left 0.999 at -24.31 dB RMS against -23.53 for 0.6.
    assert abs(_rms_db(hot) - _rms_db(moderate)) < 0.2
    assert _true_peak_db(hot) <= -0.5 + 0.1
    assert np.max(np.abs(hot)) <= 0.99 + 1e-6
