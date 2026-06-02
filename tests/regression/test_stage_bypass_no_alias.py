"""
Regression test: mastering stages never alias the caller's array on bypass (#4094, #4095)

Every stage ``apply()`` in ``auralis/core/stages/`` advertises an independent
result. On their no-op / bypass early-exit paths they used to return the
caller's ``audio`` array directly, so a caller that retained or mutated the
return value would silently corrupt its own input buffer. Each bypass path must
now return a copy. The same invariant is checked for
``HybridProcessor._process_impl``'s empty-array early return.

For each case: assert the bypass return is a distinct object that does not share
memory with the input, then mutate the result and assert the input is unchanged.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import numpy as np
import pytest

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.stages import (
    air_enhancement,
    bass_enhancement,
    clarity_boost,
    harmonic_exciter,
    mid_warmth,
    presence_enhancement,
    resonance_notches,
    safety_limiter,
    stereo_expansion,
    sub_bass_control,
    transient_shaper,
)

SR = 44100


def _audio() -> np.ndarray:
    """Quiet stereo signal (peak < safety ceiling) so all bypass guards trip."""
    n = 2048
    t = np.linspace(0.0, 1.0, n, endpoint=False)
    sig = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
    return np.column_stack([sig, sig])


# Each entry returns the array part of the stage's bypass return, given `audio`.
# Args are chosen so a no-op bypass branch is guaranteed to fire.
def _stage_calls(cfg: SimpleMasteringConfig):
    return {
        # notches=[] -> no-op
        "resonance_notches": lambda a: resonance_notches.apply(a, SR, [], False)[0],
        # intensity=0 and sub_bass below HP-activate -> no reduction, no HP
        "sub_bass_control": lambda a: sub_bass_control.apply(a, 0.0, 0.3, 0.0, SR, False, cfg)[0],
        # peak < ceiling -> no limiting
        "safety_limiter": lambda a: safety_limiter.apply(a, False),
        # intensity=0 -> nothing applied
        "bass_enhancement": lambda a: bass_enhancement.apply(a, 0.3, 0.0, SR, False, cfg)[0],
        # current_width >= 0.40 -> already wide
        "stereo_expansion": lambda a: stereo_expansion.apply(a, 0.5, 0.0, SR, False)[0],
        # neutral presence + intensity=0 -> no boost
        "presence_enhancement": lambda a: presence_enhancement.apply(a, 0.0, 0.0, 0.0, SR, False, cfg)[0],
        # bright source (presence/air maxed) -> exciter does not engage
        "harmonic_exciter": lambda a: harmonic_exciter.apply(a, 1.0, 1.0, 1.0, 0.0, SR, False, cfg)[0],
        # neutral body + intensity=0 -> no boost
        "mid_warmth": lambda a: mid_warmth.apply(a, 0.0, 0.0, 0.0, SR, False, cfg)[0],
        # bright source -> darkness_factor below activation
        "air_enhancement": lambda a: air_enhancement.apply(a, 1.0, 1.0, 0.0, SR, False, cfg)[0],
        # high crest -> transient shaper does not engage
        "transient_shaper": lambda a: transient_shaper.apply(a, 0.3, 0.3, 100.0, 0.0, SR, False, cfg)[0],
        # upper_mid above tolerance -> clarity boost not needed
        "clarity_boost": lambda a: clarity_boost.apply(a, 1.0, 0.0, SR, False, cfg)[0],
    }


@pytest.mark.parametrize("stage_name", list(_stage_calls(SimpleMasteringConfig()).keys()))
def test_stage_bypass_returns_independent_copy(stage_name):
    """Bypass paths must return a copy, never an alias of the input (#4094)."""
    cfg = SimpleMasteringConfig()
    call = _stage_calls(cfg)[stage_name]
    audio = _audio()
    original = audio.copy()

    result = call(audio)

    assert result is not audio, f"{stage_name}: bypass returned the input object"
    assert not np.may_share_memory(result, audio), (
        f"{stage_name}: bypass return shares memory with input"
    )
    # Mutating the result must not touch the caller's buffer.
    result += 1.0
    np.testing.assert_array_equal(
        audio, original, err_msg=f"{stage_name}: mutating bypass result corrupted input"
    )


def test_hybrid_processor_empty_array_returns_copy():
    """Empty-array early return must not alias the caller's array (#4095)."""
    from auralis.core.config import UnifiedConfig
    from auralis.core.hybrid_processor import HybridProcessor

    processor = HybridProcessor(UnifiedConfig())
    empty = np.empty((0, 2), dtype=np.float64)

    result = processor._process_impl(empty)

    assert result is not None
    assert len(result) == 0
    assert result is not empty
    assert not np.may_share_memory(result, empty)
