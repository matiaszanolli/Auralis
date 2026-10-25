"""
HarmonicExciter bypass threshold is shared with its stage (#6224)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#4900 made the pipeline stage report `no_op` when the exciter will bypass,
by copying the exciter's own `-60.0` bypass literal into the stage. The
coupling lived in two identical bare numbers: moving the threshold would
silently regress #4900 (the stage claiming stage_info for a stage that never
ran). Both sites now go through HarmonicExciter.BYPASS_WET_DB /
will_bypass(), and this spec ties the two behaviours together at the
threshold's edges — including that CHANGING the constant flips both
together, the acceptance criterion.
"""

import numpy as np
import pytest

from auralis.core.dsp.harmonic_exciter import HarmonicExciter
from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.stages import harmonic_exciter as exciter_stage

SR = 44100


def _audio(seconds: float = 0.5) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    sig = 0.4 * np.sin(2 * np.pi * 1000 * t)
    return np.stack([sig, sig]).astype(np.float64)


@pytest.mark.parametrize(
    "wet_db,expected_bypass",
    [
        (-80.0, True),
        (-60.0, True),    # at the threshold: bypass (<=)
        (-59.999, False),
        (-30.0, False),
    ],
)
def test_will_bypass_matches_the_exciter_bypass(wet_db, expected_bypass):
    audio = _audio()
    out = HarmonicExciter.apply(_audio(), sample_rate=SR, wet_db=wet_db)
    if expected_bypass:
        np.testing.assert_array_equal(out, audio)  # unchanged copy
    else:
        assert not np.array_equal(out, audio)      # harmonics were added
    assert HarmonicExciter.will_bypass(wet_db) is expected_bypass


def test_stage_reports_no_op_exactly_when_the_exciter_bypasses():
    """The stage's no_op boundary is the exciter's own constant, and moving
    the constant moves both together (monkeypatching stands in for an edit)."""
    config = SimpleMasteringConfig()
    audio = _audio()

    # Drive the stage's computed wet_db across the boundary by varying
    # intensity*hf_lift (wet_db = base + 20*log10(wet_mix)): very small
    # wet_mix lands at/below BYPASS_WET_DB.
    _, info_at_floor = exciter_stage.apply(
        audio.copy(), intensity=1e-4, sample_rate=SR, verbose=False,
        config=config, hf_lift=1e-4,
    )
    _, info_engaged = exciter_stage.apply(
        audio.copy(), intensity=0.8, sample_rate=SR, verbose=False,
        config=config, hf_lift=0.8,
    )
    assert info_at_floor is None, "below the threshold the stage must report no_op"
    assert info_engaged is not None

    # Changing the constant flips the exciter bypass AND the stage's no_op
    # result together — the acceptance criterion for the shared constant.
    original = HarmonicExciter.BYPASS_WET_DB
    try:
        HarmonicExciter.BYPASS_WET_DB = -30.0
        # A wet level between -60 and the new -30 threshold: previously ran,
        # now must bypass everywhere it is consulted.
        assert HarmonicExciter.will_bypass(-45.0) is True
        _, info = exciter_stage.apply(
            audio.copy(), intensity=0.02, sample_rate=SR, verbose=False,
            config=config, hf_lift=0.5,  # wet_db lands near -45..-50
        )
        assert info is None, "stage must follow the moved constant (#6224)"
    finally:
        HarmonicExciter.BYPASS_WET_DB = original
