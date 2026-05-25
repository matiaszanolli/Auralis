"""
Regression test for #3448 — spectrum analyzer instances must NOT share mutable state.

The issue title named `StreamingSpectralAnalyzer`, but on inspection that
class (auralis/analysis/fingerprint/analyzers/streaming/spectral.py) has
no `smoothing_buffer` attribute at all. The real `smoothing_buffer` lives
on `BaseSpectrumAnalyzer` (auralis/analysis/base_spectrum_analyzer.py:59)
and is correctly initialized in `__init__` — instances are already
isolated.

These tests pin that contract so a future refactor that accidentally
moves `smoothing_buffer` (or any other per-instance buffer) to a
class-level default would be caught immediately.
"""

from __future__ import annotations

import numpy as np
import pytest

from auralis.analysis.base_spectrum_analyzer import BaseSpectrumAnalyzer
from auralis.analysis.fingerprint.analyzers.streaming.spectral import (
    StreamingSpectralAnalyzer,
)
from auralis.analysis.parallel_spectrum_analyzer import ParallelSpectrumAnalyzer


def test_parallel_spectrum_analyzer_instances_are_isolated():
    """Mutating one instance's smoothing_buffer must not affect another."""
    a = ParallelSpectrumAnalyzer()
    b = ParallelSpectrumAnalyzer()

    assert a is not b
    assert a.smoothing_buffer is None and b.smoothing_buffer is None

    a.smoothing_buffer = np.zeros(64)
    assert b.smoothing_buffer is None, (
        "Instance isolation violated: setting smoothing_buffer on `a` "
        "leaked to `b` — #3448 regressed (class-level mutable default?)"
    )

    # Mutate `a`'s buffer in-place — `b`'s should still be None
    a.smoothing_buffer[0] = 1.0
    assert b.smoothing_buffer is None


def test_streaming_spectral_analyzer_per_instance_buffers():
    """StreamingSpectralAnalyzer has audio_buffer, magnitude_buffer, and a
    SpectralMoments instance. None should be shared across instances."""
    a = StreamingSpectralAnalyzer()
    b = StreamingSpectralAnalyzer()

    assert a is not b
    assert a.audio_buffer is not b.audio_buffer, (
        "audio_buffer is shared — class-level mutable default"
    )
    assert a.magnitude_buffer is not b.magnitude_buffer, (
        "magnitude_buffer is shared — class-level mutable default"
    )
    assert a.spectral_moments is not b.spectral_moments, (
        "spectral_moments is shared — class-level mutable default"
    )

    # Mutate `a`'s state, confirm `b` unaffected
    a.audio_buffer.extend([1.0, 2.0, 3.0])
    assert len(b.audio_buffer) == 0


def test_streaming_spectral_analyzer_does_not_carry_smoothing_buffer():
    """Issue's named field doesn't exist on this class. If it's ever added,
    this test is the place to also assert it's per-instance."""
    analyzer = StreamingSpectralAnalyzer()
    assert not hasattr(analyzer, 'smoothing_buffer'), (
        "If you've added smoothing_buffer to StreamingSpectralAnalyzer, "
        "extend test_streaming_spectral_analyzer_per_instance_buffers to "
        "verify it's per-instance — #3448"
    )


@pytest.mark.parametrize("cls", [BaseSpectrumAnalyzer, ParallelSpectrumAnalyzer])
def test_spectrum_analyzer_static_attribute_dict_has_no_smoothing_buffer(cls):
    """The class object itself must NOT carry `smoothing_buffer` as a
    class-level attribute (only instances should via __init__).

    This is the structural check that complements the behavioral tests
    above. Skips BaseSpectrumAnalyzer instantiation (it's abstract); just
    inspects the class dict.
    """
    # Class __dict__ should NOT contain smoothing_buffer (only __init__ should
    # set it on each instance). Type annotations live in __annotations__.
    assert 'smoothing_buffer' not in cls.__dict__, (
        f"{cls.__name__}.smoothing_buffer is a class-level attribute — "
        "all instances will share it. Move to __init__."
    )
