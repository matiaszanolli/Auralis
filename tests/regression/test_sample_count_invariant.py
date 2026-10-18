"""
Regression test: runtime sample count assertion in HybridProcessor (#2369, #2519)

Verifies that the brick-wall limiter in HybridProcessor preserves sample count.
A shape mismatch raises RuntimeError (fail-fast, and immune to python -O,
#5533) rather than silently
producing misaligned gapless audio.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch


class TestSampleCountInvariant:
    """Regression: limiter must preserve sample count (#2519)."""

    def test_invariant_check_present_in_source(self):
        """Verify the sample-count check exists in adaptive mode (#5533: it
        must be a raise, not an assert — asserts vanish under python -O)."""
        import inspect
        from auralis.core.hybrid_processor import HybridProcessor
        source = inspect.getsource(HybridProcessor._process_adaptive_mode)
        assert "if processed.shape != target_audio.shape:" in source, (
            "Sample-count check missing from _process_adaptive_mode"
        )
        assert "raise RuntimeError(" in source, (
            "Sample-count check must raise, not assert"
        )

    def test_invariant_check_present_in_hybrid_mode(self):
        """Verify the sample-count check exists in hybrid mode too."""
        import inspect
        from auralis.core.hybrid_processor import HybridProcessor
        source = inspect.getsource(HybridProcessor._process_hybrid_mode)
        assert "if processed.shape != target_audio.shape:" in source, (
            "Sample-count check missing from _process_hybrid_mode"
        )
        assert "raise RuntimeError(" in source, (
            "Sample-count check must raise, not assert"
        )

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
