"""
Regression test: runtime sample count assertion in the mode pipelines (#2369, #2519)

Verifies that the brick-wall limiter preserves sample count: a limiter that
returns a different shape must raise RuntimeError (fail-fast, and immune to
python -O, #5533) rather than silently producing misaligned gapless audio.

The adaptive and hybrid guards are exercised behaviorally — a limiter stub
that drops one sample — rather than by pinning production source text, so
the checks can move between modules without breaking the test (#6272,
#6244). They live in auralis/core/processing/mode_dispatch.py; the
reference-mode guard lives in auralis/core/hybrid_stage_dispatch.py and has
its behavioral test in tests/auralis/core/test_post_limiter_invariants_5533.py.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import re

import numpy as np
import pytest


class _SampleDroppingLimiter:
    """Stands in for BrickWallLimiter with the invariant broken."""

    def process(self, audio):
        return audio[..., :-1].copy()


class _PassThroughStage:
    """Stands in for continuous_mode / hybrid_mode: returns its input."""

    last_fingerprint = None
    last_coordinates = None
    last_parameters = None

    def process(self, audio, *_args, **_kwargs):
        return audio


class _Processor:
    """Just the attributes auralis.core.processing.mode_dispatch reads."""

    current_targets = None
    eq_processor = None
    continuous_mode = _PassThroughStage()
    hybrid_mode = _PassThroughStage()
    brick_wall_limiter = _SampleDroppingLimiter()


_TARGET = np.zeros((2, 64), dtype=np.float32)


class TestSampleCountInvariant:
    """Regression: limiter must preserve sample count (#2519)."""

    @pytest.mark.parametrize("mode", ["adaptive", "hybrid"])
    def test_limiter_shape_change_raises(self, mode):
        """A limiter that drops a sample aborts the pipeline with
        RuntimeError (#5533: it must be a raise, not an assert — asserts
        vanish under python -O)."""
        from auralis.core.processing import mode_dispatch

        with pytest.raises(
            RuntimeError,
            match=re.escape(f"Sample count mismatch after limiter ({mode})"),
        ):
            if mode == "adaptive":
                mode_dispatch.process_adaptive_mode(_Processor(), _TARGET.copy())
            else:
                mode_dispatch.process_hybrid_mode(_Processor(), _TARGET.copy(), None)

    def test_limiter_preserves_shape_mono(self):
        """Brick-wall limiter must not change mono sample count."""
        from auralis.dsp.dynamics.brick_wall_limiter import (
            BrickWallLimiter,
            BrickWallLimiterSettings,
        )
        limiter = BrickWallLimiter(BrickWallLimiterSettings())
        audio = np.random.randn(44100).astype(np.float32) * 2.0  # May clip
        result = limiter.process(audio)
        assert result.shape == audio.shape

    def test_limiter_preserves_shape_stereo(self):
        """Brick-wall limiter must not change stereo sample count."""
        from auralis.dsp.dynamics.brick_wall_limiter import (
            BrickWallLimiter,
            BrickWallLimiterSettings,
        )
        limiter = BrickWallLimiter(BrickWallLimiterSettings())
        audio = np.random.randn(44100, 2).astype(np.float32) * 2.0
        result = limiter.process(audio)
        assert result.shape == audio.shape
