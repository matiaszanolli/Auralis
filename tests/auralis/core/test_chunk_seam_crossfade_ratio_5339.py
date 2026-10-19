"""Chunk-seam crossfade-vs-settle-time ratio (#5339).

The mastering chunk loop restarts the loudness limiter's and the transient
shaper's envelopes fresh on every chunk, so the crossfade between chunks must
outlast those envelopes' settle time or every 30-second seam becomes an
audible step. SimpleMasteringConfig.__post_init__ enforces the ratio; these
tests pin the current constants as satisfying it and pin that the assertion
engages when any one constant is tuned in isolation.
"""

import dataclasses

import pytest

from auralis.core.mastering_config import (
    _SEAM_SAFETY_FACTOR,
    _SEAM_SETTLE_TAUS,
    SimpleMasteringConfig,
)


def test_current_constants_satisfy_the_seam_ratio_with_margin():
    """The shipped crossfade must clear the enforced floor — and by a real
    margin, not by luck, so ordinary retuning doesn't land on the boundary."""
    config = SimpleMasteringConfig()
    slowest_tau_ms = max(
        config.TRANSIENT_SLOW_MS, config.LOUDNESS_LIMITER_RELEASE_MS
    )
    floor = _SEAM_SETTLE_TAUS * _SEAM_SAFETY_FACTOR * slowest_tau_ms / 1000.0
    assert config.CROSSFADE_DURATION_SEC >= floor
    assert config.CROSSFADE_DURATION_SEC >= 2 * floor


def test_shortening_the_crossfade_in_isolation_is_rejected():
    with pytest.raises(AssertionError, match="audible steps"):
        dataclasses.replace(SimpleMasteringConfig(), CROSSFADE_DURATION_SEC=0.01)


def test_lengthening_the_limiter_release_in_isolation_is_rejected():
    with pytest.raises(AssertionError, match="audible steps"):
        dataclasses.replace(SimpleMasteringConfig(), LOUDNESS_LIMITER_RELEASE_MS=5000.0)


def test_lengthening_the_transient_slow_envelope_in_isolation_is_rejected():
    with pytest.raises(AssertionError, match="audible steps"):
        dataclasses.replace(SimpleMasteringConfig(), TRANSIENT_SLOW_MS=5000.0)


def test_stage_wiring_passes_config_envelope_times_to_the_shaper():
    """The shaper's per-chunk-reset envelope constants are part of the seam
    ratio, so the stage must route the config values through rather than
    silently falling back to TransientShaper.apply()'s function defaults —
    otherwise a config retune would not move the real envelopes."""
    import inspect

    from auralis.core.stages import transient_shaper as stage

    source = inspect.getsource(stage)
    assert "config.TRANSIENT_FAST_MS" in source
    assert "config.TRANSIENT_SLOW_MS" in source
