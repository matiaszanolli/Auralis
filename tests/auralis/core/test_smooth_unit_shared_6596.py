"""One guarded S-curve and one set of calibration constants for every mastering stage (#6596).

``0.5 + 0.5 * tanh(...)`` was hand-written at nine sites; only continuous_space's copy mapped NaN to
the neutral midpoint (#5505) and saturated on ±Inf (#5534). AdaptiveMode's crest coordinate is NaN
on a silent window (``-inf - -inf``), which reached the compression and expansion amounts.
"""

import math
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.processing.adaptive_mode import AdaptiveMode
from auralis.core.processing.continuous_space import ProcessingSpaceMapper
from auralis.core.utils import smooth_curves
from auralis.core.utils.smooth_curves import smooth_unit


@pytest.mark.parametrize("width", [4.0, 3.0, 0.7, 1234.5])
@pytest.mark.parametrize("x", [-30.0, 0.0, 13.4, 16.0, 99.0])
def test_the_width_form_is_the_same_curve(x, width):
    """``tanh((x - c) / width)`` sites now call ``smooth_unit(x, c, width / 2)``: same numbers."""
    assert smooth_unit(x, 16.0, width / 2.0) == pytest.approx(0.5 + 0.5 * math.tanh((x - 16.0) / width), abs=1e-15)


def test_undefined_and_extreme_inputs():
    assert smooth_unit(float("nan"), 0.0, 1.0) == 0.5
    assert smooth_unit(np.float64("inf"), 0.0, 1.0) == 1.0
    assert smooth_unit(-math.inf, 0.0, 1.0) == 0.0


def test_the_continuous_mapper_uses_the_shared_calibration():
    assert ProcessingSpaceMapper._CREST_CENTER_DB == smooth_curves.CREST_CENTER_DB
    assert ProcessingSpaceMapper._CREST_SCALE_DB == smooth_curves.CREST_SCALE_DB


def test_adaptive_dynamics_on_silence_stays_finite():
    mode = AdaptiveMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        target_generator=MagicMock(),
        spectrum_mapper=MagicMock(),
    )
    params = SimpleNamespace(compression_amount=0.4, expansion_amount=0.2)
    silence = np.zeros((2, 44100), dtype=np.float32)

    out = mode._apply_dynamics_processing(silence, params)

    assert math.isfinite(params.compression_amount)
    assert math.isfinite(params.expansion_amount)
    assert 0.0 <= params.compression_amount <= 0.4
    assert out.shape == silence.shape
    assert np.isfinite(out).all()
