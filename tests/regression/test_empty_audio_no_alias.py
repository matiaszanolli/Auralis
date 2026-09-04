"""
Regression: Empty-audio early-return must not alias input (#2911)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Four DSP components returned the original array on empty-input guards.
AdaptiveLimiter was deleted as unreachable in #4873 and DynamicsProcessor's
orphaned processing path was retired in #5295; the remaining two are covered
here. Returning aliases violates the project-wide invariant that DSP functions
produce independent output buffers.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.brick_wall_limiter import (
    BrickWallLimiter,
    BrickWallLimiterSettings,
)
from auralis.dsp.dynamics.compressor import AdaptiveCompressor
from auralis.dsp.dynamics.settings import CompressorSettings


@pytest.fixture
def empty_audio():
    return np.array([], dtype=np.float32)


class TestEmptyAudioNoAlias:
    """Each DSP component must return a copy (not the same object) for empty input."""

    def test_brick_wall_limiter(self, empty_audio):
        limiter = BrickWallLimiter(BrickWallLimiterSettings())
        result = limiter.process(empty_audio)
        assert result is not empty_audio

    def test_compressor(self, empty_audio):
        compressor = AdaptiveCompressor(CompressorSettings(), sample_rate=44100)
        result, info = compressor.process(empty_audio)
        assert result is not empty_audio
        assert info == {}
