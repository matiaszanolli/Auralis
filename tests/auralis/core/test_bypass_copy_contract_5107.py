"""
Maybe-process bypass paths copy, like stages.no_op() (#5107).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``auralis/core/stages/__init__.py`` defines ``no_op(audio) -> (audio.copy(), None)``
specifically so every early-return bypass "never hands back the caller's array",
and all 13 named stages honour it. Four maybe-process functions one package over
implemented the same shape but returned the literal input object on their
"nothing to do" branch.

Latent rather than live: every current call site was traced to an entry point
beginning ``processed_audio = target_audio.copy()`` with only allocating stages
in between, so no caller-owned buffer was exposed. The hazard is that the
guarantee lived in the call sites rather than in these functions — any future
direct caller, or a refactor moving them earlier in the chain, silently gets a
caller-owned array back and a downstream in-place op corrupts it.

The identity assertions below are the contract; the mutation assertions are why
it matters.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.core.mastering_process_chunk import reduce_peaks
from auralis.core.processing.base.peak_management import PeakNormalizer, SafetyLimiter
from auralis.core.processing.hf_aware_limiter import apply_hf_aware_limiter


def _quiet_stereo():
    """Peak well under SAFETY_THRESHOLD_DB (-0.1 dBFS) — takes every bypass."""
    return np.full((2, 512), 0.1, dtype=np.float32)


class TestSafetyLimiterBypass:
    def test_returns_a_copy_not_the_input(self):
        audio = _quiet_stereo()
        out, applied = SafetyLimiter.apply_if_needed(audio)
        assert applied is False
        assert out is not audio
        assert np.array_equal(out, audio)

    def test_writing_to_the_result_does_not_touch_the_input(self):
        audio = _quiet_stereo()
        out, _ = SafetyLimiter.apply_if_needed(audio)
        out[:] = 0.9
        assert np.allclose(audio, 0.1), "caller's buffer was mutated through the result"

    def test_shape_and_dtype_preserved(self):
        audio = _quiet_stereo()
        out, _ = SafetyLimiter.apply_if_needed(audio)
        assert out.shape == audio.shape
        assert out.dtype == audio.dtype


class TestHFAwareLimiterBypass:
    def test_returns_a_copy_not_the_input(self):
        audio = _quiet_stereo()
        out, applied = apply_hf_aware_limiter(audio, sample_rate=44100, shelf_db=3.0)
        assert applied is False
        assert out is not audio
        assert np.array_equal(out, audio)

    def test_writing_to_the_result_does_not_touch_the_input(self):
        audio = _quiet_stereo()
        out, _ = apply_hf_aware_limiter(audio, sample_rate=44100, shelf_db=3.0)
        out[:] = 0.9
        assert np.allclose(audio, 0.1)

    def test_shape_and_dtype_preserved(self):
        audio = _quiet_stereo()
        out, _ = apply_hf_aware_limiter(audio, sample_rate=44100, shelf_db=3.0)
        assert out.shape == audio.shape
        assert out.dtype == audio.dtype


class TestReducePeaksBypass:
    """Sibling named in the issue."""

    def test_returns_a_copy_when_already_under_target(self):
        audio = _quiet_stereo()
        out, peak_db = reduce_peaks(audio, current_db=-20.0, target_db=-1.0)
        assert out is not audio
        assert np.array_equal(out, audio)
        assert peak_db == -20.0

    def test_writing_to_the_result_does_not_touch_the_input(self):
        audio = _quiet_stereo()
        out, _ = reduce_peaks(audio, current_db=-20.0, target_db=-1.0)
        out[:] = 0.9
        assert np.allclose(audio, 0.1)


class TestPeakNormalizerBypass:
    """Fourth site, found by the sibling sweep — not listed in the issue."""

    def test_returns_a_copy_for_near_silent_input(self):
        audio = np.full((2, 512), 0.0005, dtype=np.float32)  # peak <= 0.001
        out, _ = PeakNormalizer.normalize_to_target(audio, target_peak_db=-1.0)
        assert out is not audio
        assert np.array_equal(out, audio)

    def test_writing_to_the_result_does_not_touch_the_input(self):
        audio = np.full((2, 512), 0.0005, dtype=np.float32)
        out, _ = PeakNormalizer.normalize_to_target(audio, target_peak_db=-1.0)
        out[:] = 0.9
        assert np.allclose(audio, 0.0005)


class TestActiveBranchesUnchanged:
    """The fix must not add a second copy on the processing branch."""

    def test_safety_limiter_still_limits_a_hot_signal(self):
        audio = np.full((2, 512), 0.999, dtype=np.float32)
        out, applied = SafetyLimiter.apply_if_needed(audio)
        assert applied is True
        assert out.shape == audio.shape
        assert out.dtype == audio.dtype
        assert np.max(np.abs(out)) < np.max(np.abs(audio))

    def test_reduce_peaks_still_reduces(self):
        audio = np.full((2, 512), 0.999, dtype=np.float32)
        out, peak_db = reduce_peaks(audio, current_db=-0.01, target_db=-3.0)
        assert out is not audio
        assert peak_db < -0.01

    @pytest.mark.parametrize("value", [0.1, 0.5])
    def test_peak_normalizer_still_normalizes(self, value):
        audio = np.full((2, 512), value, dtype=np.float32)
        out, _ = PeakNormalizer.normalize_to_target(audio, target_peak_db=-6.0)
        expected = 10 ** (-6.0 / 20.0)
        assert np.max(np.abs(out)) == pytest.approx(expected, rel=1e-4)
