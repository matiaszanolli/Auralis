"""
Regression test: runtime sample count assertion in HybridProcessor (#2369, #2519)

Verifies that the brick-wall limiter in HybridProcessor preserves sample count.
A shape mismatch triggers an AssertionError (fail-fast) rather than silently
producing misaligned gapless audio.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch


class TestSampleCountInvariant:
    """Regression: limiter must preserve sample count (#2519)."""

    def test_assertion_present_in_source(self):
        """Verify the assertion exists in the source code."""
        import inspect
        from auralis.core.hybrid_processor import HybridProcessor
        source = inspect.getsource(HybridProcessor._process_adaptive_mode)
        assert "processed.shape == target_audio.shape" in source, (
            "Sample-count assertion missing from _process_adaptive_mode"
        )

    def test_assertion_present_in_hybrid_mode(self):
        """Verify the assertion exists in hybrid mode too."""
        import inspect
        from auralis.core.hybrid_processor import HybridProcessor
        source = inspect.getsource(HybridProcessor._process_hybrid_mode)
        assert "processed.shape == target_audio.shape" in source, (
            "Sample-count assertion missing from _process_hybrid_mode"
        )

    def test_limiter_preserves_shape_mono(self):
        """Brick-wall limiter must not change mono sample count."""
        from auralis.dsp.dynamics.brick_wall_limiter import BrickWallLimiter
        limiter = BrickWallLimiter()
        audio = np.random.randn(44100).astype(np.float32) * 2.0  # May clip
        result = limiter.process(audio)
        assert result.shape == audio.shape

    def test_limiter_preserves_shape_stereo(self):
        """Brick-wall limiter must not change stereo sample count."""
        from auralis.dsp.dynamics.brick_wall_limiter import BrickWallLimiter
        limiter = BrickWallLimiter()
        audio = np.random.randn(44100, 2).astype(np.float32) * 2.0
        result = limiter.process(audio)
        assert result.shape == audio.shape
