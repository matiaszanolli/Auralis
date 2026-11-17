"""The compressor's soft-knee static curve is continuous and monotonic (#6301).

The in-knee branch used a soft-ratio form that did not join the linear region: at the top knee edge it returned
-knee*(r-1)/(2r-1) against the linear branch's -knee*(r-1)/(2r), so crossing the edge gave LESS gain reduction
for MORE input. It is now the standard quadratic knee.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.compressor import AdaptiveCompressor, CompressorSettings


def _compressor(ratio: float, knee_db: float, threshold_db: float = -20.0) -> AdaptiveCompressor:
    return AdaptiveCompressor(
        CompressorSettings(
            threshold_db=threshold_db, ratio=ratio, attack_ms=10.0, release_ms=100.0,
            knee_db=knee_db, makeup_gain_db=0.0, enable_lookahead=False,
        ),
        44100,
    )


@pytest.mark.parametrize("ratio", [2.0, 4.0, 10.0])
@pytest.mark.parametrize("knee_db", [2.0, 6.0, 12.0])
def test_gain_reduction_has_no_jump_at_either_knee_edge(ratio, knee_db):
    comp = _compressor(ratio, knee_db)
    lo, hi = -20.0 - knee_db / 2, -20.0 + knee_db / 2
    eps = 1e-6

    edges = comp._calculate_gain_reduction_vectorized(np.array([lo - eps, lo + eps, hi - eps, hi + eps]))

    assert abs(edges[1] - edges[0]) < 0.01
    assert abs(edges[3] - edges[2]) < 0.01


@pytest.mark.parametrize("ratio", [2.0, 4.0, 10.0])
def test_more_input_never_gives_less_gain_reduction(ratio):
    comp = _compressor(ratio, knee_db=8.0)
    levels = np.linspace(-40.0, 0.0, 4001)

    reduction = comp._calculate_gain_reduction_vectorized(levels)

    assert np.all(np.diff(reduction) <= 1e-9)  # non-increasing (reduction grows more negative)


def test_the_curve_matches_the_hard_knee_formula_outside_the_knee():
    comp = _compressor(ratio=4.0, knee_db=6.0)

    out = comp._calculate_gain_reduction_vectorized(np.array([-30.0, -10.0]))

    assert out[0] == 0.0
    assert out[1] == pytest.approx(-(10.0) * (1 - 1 / 4.0))
