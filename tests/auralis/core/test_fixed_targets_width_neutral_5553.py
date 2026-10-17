"""#5553 — fixed targets must leave the stereo image alone.

``stereo_width_target`` is a width FACTOR (side gain = 2 * factor), so unity is
``WIDTH_FACTOR_UNITY`` (0.5). ``convert_targets_to_parameters`` used 1.0 with a
"preserve width" comment, which is the maximum widening: the side channel rose
+5.3 dB on quiet-peak sources and not at all on loud ones (the peak gate), so
the image jumped between chunks.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.processing.continuous_mode import ContinuousMode
from auralis.core.processing.fixed_target_params import convert_targets_to_parameters
from auralis.dsp.utils.stereo import WIDTH_FACTOR_UNITY

SR = 44100


def _mode() -> ContinuousMode:
    return ContinuousMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        fingerprint_analyzer=MagicMock(),
    )


def _stereo(peak: float, seconds: float = 3.0) -> np.ndarray:
    rng = np.random.default_rng(3)
    n = int(SR * seconds)
    mid = rng.standard_normal(n)
    side = 0.4 * rng.standard_normal(n)
    x = np.column_stack([mid + side, mid - side])
    return (x / np.max(np.abs(x)) * peak).astype(np.float32)


def _side_rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(((x[:, 0] - x[:, 1]) / 2) ** 2)))


def test_fixed_targets_use_the_neutral_width_factor() -> None:
    params = convert_targets_to_parameters({'target_lufs': -14.0})
    assert params.stereo_width_target == WIDTH_FACTOR_UNITY


@pytest.mark.parametrize("peak", [0.25, 0.5, 0.9])
def test_fixed_targets_do_not_change_side_level(peak: float) -> None:
    audio = _stereo(peak)
    params = convert_targets_to_parameters({'target_lufs': -14.0})
    out = _mode()._apply_stereo_width(audio, params)
    assert out.shape == audio.shape
    ratio_db = 20 * np.log10(_side_rms(out) / _side_rms(audio))
    assert ratio_db == pytest.approx(0.0, abs=0.1)
