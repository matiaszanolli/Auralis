"""
EQ Overlap-Add Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for commit a448e021 (issue #2680):
EQ overlap-add must use += (accumulate) not = (overwrite).

With a Hann window at 50% overlap, COLA (Constant Overlap-Add) guarantees
that the sum of overlapping windows equals unity. If the overlap regions
are overwritten instead of accumulated, the first half of each overlap
is lost and the output contains discontinuities.
"""

from unittest.mock import patch

import numpy as np
import pytest

from auralis.core.processing.eq_processor import EQProcessor
from auralis.dsp.psychoacoustic_eq import EQSettings, PsychoacousticEQ


def _identity_chunk(self, chunk, target_curve, content_profile=None):
    """Identity processing — returns input unchanged."""
    return chunk.copy()


def _zero_curve(self, eq_curve):
    """Return a zero target curve to bypass real curve conversion."""
    num_bands = len(self.psychoacoustic_eq.critical_bands)
    return np.zeros(num_bands)


@pytest.mark.regression
class TestEQOverlapAdd:
    """Regression tests for EQ overlap-add accumulation (issue #2680)."""

    def _make_processor(self, sample_rate=44100):
        settings = EQSettings(sample_rate=sample_rate, fft_size=4096)
        eq = PsychoacousticEQ(settings)
        return EQProcessor(eq)

    def _patches(self):
        """Patch EQ to identity processing, bypassing curve conversion."""
        return (
            patch.object(PsychoacousticEQ, 'process_realtime_chunk', _identity_chunk),
            patch.object(EQProcessor, '_eq_curve_to_array', _zero_curve),
        )

    def test_overlap_add_reconstructs_signal_stereo(self):
        """
        With identity EQ and Hann window at 50% overlap, COLA guarantees
        perfect reconstruction. This fails if += is changed back to =.
        """
        processor = self._make_processor()
        fft_size = processor.psychoacoustic_eq.fft_size
        num_samples = fft_size * 4
        audio = np.random.RandomState(42).randn(num_samples, 2).astype(np.float64)

        p1, p2 = self._patches()
        with p1, p2:
            result = processor._process_with_psychoacoustic_eq(audio, {})

        # COLA with Hann at 50% overlap sums to 1.0 in the interior
        half = fft_size // 2
        interior = slice(half, num_samples - half)
        # np.hanning is not perfectly COLA (~0.9996 min), so use atol=1e-3.
        # With = instead of +=, error would be ~0.5 (half the signal lost).
        np.testing.assert_allclose(
            result[interior], audio[interior],
            atol=2e-3,
            err_msg="Overlap-add failed to reconstruct signal — likely using = instead of +=",
        )

    def test_overlap_add_reconstructs_signal_mono(self):
        """Same test for mono audio path."""
        processor = self._make_processor()
        fft_size = processor.psychoacoustic_eq.fft_size
        num_samples = fft_size * 4
        audio = np.random.RandomState(42).randn(num_samples).astype(np.float64)

        p1, p2 = self._patches()
        with p1, p2:
            result = processor._process_with_psychoacoustic_eq(audio, {})

        half = fft_size // 2
        interior = slice(half, num_samples - half)
        np.testing.assert_allclose(
            result[interior], audio[interior],
            atol=2e-3,
            err_msg="Overlap-add failed to reconstruct mono signal",
        )

    def test_overlap_regions_are_accumulated(self):
        """
        Directly verify that overlap regions receive contributions from
        two adjacent chunks. With = instead of +=, the overlap region
        would only contain the second chunk's contribution.
        """
        processor = self._make_processor()
        fft_size = processor.psychoacoustic_eq.fft_size
        hop = fft_size // 2

        num_samples = fft_size * 3
        audio = np.ones((num_samples, 2), dtype=np.float64)

        p1, p2 = self._patches()
        with p1, p2:
            result = processor._process_with_psychoacoustic_eq(audio, {})

        # In the overlap region [hop, fft_size), both chunk 0 and chunk 1
        # contribute. With Hann window COLA, their sum should be 1.0.
        # With = (overwrite), only chunk 1's window would be present.
        overlap_region = result[hop:fft_size]
        expected = np.ones_like(overlap_region)
        np.testing.assert_allclose(
            overlap_region, expected,
            atol=2e-3,
            err_msg="Overlap region not properly accumulated — likely using = instead of +=",
        )
