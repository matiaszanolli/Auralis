"""
Regression: Empty-audio early-return must not alias input (#2911)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Four DSP components returned the original array on empty-input guard
clauses. This violated the project-wide invariant that DSP functions
never return an alias to their input, risking silent corruption when
callers mutate the returned buffer.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.dsp.advanced_dynamics import DynamicsProcessor, DynamicsSettings
from auralis.dsp.dynamics.brick_wall_limiter import (
    BrickWallLimiter,
    BrickWallLimiterSettings,
)
from auralis.dsp.dynamics.compressor import AdaptiveCompressor
from auralis.dsp.dynamics.limiter import AdaptiveLimiter
from auralis.dsp.dynamics.settings import CompressorSettings, LimiterSettings


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

    def test_limiter(self, empty_audio):
        limiter = AdaptiveLimiter(LimiterSettings(), sample_rate=44100)
        result, info = limiter.process(empty_audio)
        assert result is not empty_audio
        assert info == {}

    def test_dynamics_processor(self, empty_audio):
        processor = DynamicsProcessor(DynamicsSettings())
        result, info = processor.process(empty_audio)
        assert result is not empty_audio
        assert info == {}
