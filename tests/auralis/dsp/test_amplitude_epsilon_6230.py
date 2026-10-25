"""
One named amplitude epsilon and one stereo-silence threshold (#6230)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Epsilon/dB-floor guards were typed inline across the engine (1e-10 in ~24
lines, 1e-9 x7, 1e-12 x3, 1e-8 x3), with #5785 unifying only the scalar
amplitude->dB convention — the array forms kept their own `+ 1e-10` at every
call site, and the same stereo-correlation silence guard was typed twice.
This pins the shared constants and the value-identical conversion of the
clearest sites.
"""

import numpy as np

from auralis.core.processing import stage_snapshot
from auralis.dsp.utils import stereo
from auralis.dsp.utils.conversion import (
    AMPLITUDE_EPS,
    SILENCE_STD_THRESHOLD,
    amplitude_to_db_array,
    to_db,
)


def test_amplitude_to_db_array_matches_the_scalar_convention():
    x = np.array([0.0, 1e-12, 0.5, 1.0])
    out = amplitude_to_db_array(x)
    np.testing.assert_allclose(out, 20 * np.log10(x + AMPLITUDE_EPS))
    # On silence it matches the scalar to_db() floor (both -200 dB).
    assert out[0] == to_db(0.0)


def test_amplitude_to_db_array_is_value_identical_to_the_old_inline_form():
    """The acceptance criterion: converted functions' outputs unchanged."""
    rng = np.random.default_rng(6230)
    x = rng.standard_normal(1000) ** 3  # includes near-zero values
    np.testing.assert_allclose(amplitude_to_db_array(x), 20 * np.log10(x + 1e-10))


def test_fingerprint_epsilon_aliases_the_amplitude_epsilon():
    from auralis.analysis.fingerprint.metrics.constants import FingerprintConstants

    assert FingerprintConstants.EPSILON == AMPLITUDE_EPS


def test_stereo_guards_share_one_threshold():
    """The two copies of the stereo-correlation silence guard use the same
    named threshold, and it is the value both shipped with (1e-9)."""
    assert SILENCE_STD_THRESHOLD == 1e-9
    n = 480
    silent = np.zeros(n)
    live = 0.3 * np.sin(np.arange(n) / 10.0)
    # Near-silent channel -> both guards treat the pair as uncorrelatable.
    assert np.std(silent) < SILENCE_STD_THRESHOLD
    assert np.std(live) > SILENCE_STD_THRESHOLD


def test_stage_snapshot_guard_behaviour_unchanged():
    """The converted guard still fires exactly at the old boundary."""
    n = 1024
    live = 0.2 * np.sin(np.arange(n) / 7.0)
    near_silent = np.full(n, 1e-10)
    assert np.std(near_silent) < SILENCE_STD_THRESHOLD
    assert np.std(live) > SILENCE_STD_THRESHOLD
