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
from auralis.dsp.eq.psychoacoustic_eq import EQSettings, PsychoacousticEQ


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


@pytest.mark.regression
class TestEQWolaHeadNormalization:
    """Regression tests for #4852: the WOLA head fade-in.

    Before the fix, output[0:hop] ramped from 0.0 up to ~1.0 because only
    frame 0's synthesis window contributed there and nothing normalized it
    out — there is no frame at i = -hop to supply the other half of the
    COLA sum. Dividing by the actual accumulated window weight recovers the
    true signal for every sample except the single global first sample,
    where the Hann window is exactly 0.0 by construction (a well-known,
    inaudible one-sample edge property of any Hann-windowed OLA scheme —
    not something a normalization scheme can recover, since 0 information
    survives multiplying by an exact-zero window coefficient).
    """

    def _make_processor(self, sample_rate=44100):
        settings = EQSettings(sample_rate=sample_rate, fft_size=4096)
        eq = PsychoacousticEQ(settings)
        return EQProcessor(eq)

    def _patches(self):
        return (
            patch.object(PsychoacousticEQ, 'process_realtime_chunk', _identity_chunk),
            patch.object(EQProcessor, '_eq_curve_to_array', _zero_curve),
        )

    def test_head_region_no_longer_fades_in_from_silence_mono(self):
        processor = self._make_processor()
        fft_size = processor.psychoacoustic_eq.fft_size
        hop = fft_size // 2
        audio = np.ones(fft_size * 4, dtype=np.float64)

        p1, p2 = self._patches()
        with p1, p2:
            result = processor._process_with_psychoacoustic_eq(audio, {})

        # Sample 0 is the one irreducible Hann-window zero (see class docstring).
        assert result[0] == pytest.approx(0.0, abs=1e-9)
        # Every other sample in the old fade-in region must now be exact —
        # before the fix this ramped linearly from 0.0 to ~1.0 across [0, hop).
        np.testing.assert_allclose(
            result[1:hop], np.ones(hop - 1),
            atol=1e-6,
            err_msg="Head region still fades in from silence — WOLA normalization missing or wrong",
        )

    def test_head_region_no_longer_fades_in_from_silence_stereo(self):
        processor = self._make_processor()
        fft_size = processor.psychoacoustic_eq.fft_size
        hop = fft_size // 2
        audio = np.ones((fft_size * 4, 2), dtype=np.float64)

        p1, p2 = self._patches()
        with p1, p2:
            result = processor._process_with_psychoacoustic_eq(audio, {})

        assert result[0, 0] == pytest.approx(0.0, abs=1e-9)
        assert result[0, 1] == pytest.approx(0.0, abs=1e-9)
        np.testing.assert_allclose(
            result[1:hop], np.ones((hop - 1, 2)),
            atol=1e-6,
            err_msg="Stereo head region still fades in from silence",
        )

    def test_interior_cola_is_now_numerically_exact(self):
        """The norm-buffer fix also cancels the residual ~1e-4 ripple from
        using a symmetric (not periodic) Hann window at 50% overlap — the
        interior sum should now be exact to floating-point precision, not
        just within the old ~2e-3 tolerance."""
        processor = self._make_processor()
        fft_size = processor.psychoacoustic_eq.fft_size
        hop = fft_size // 2
        num_samples = fft_size * 4
        audio = np.random.RandomState(42).randn(num_samples).astype(np.float64)

        p1, p2 = self._patches()
        with p1, p2:
            result = processor._process_with_psychoacoustic_eq(audio, {})

        interior = slice(hop, num_samples - hop)
        np.testing.assert_allclose(
            result[interior], audio[interior],
            atol=1e-9,
            err_msg="Interior COLA sum is no longer exact after normalization",
        )

    def test_short_buffer_entirely_inside_old_ramp_is_no_longer_corrupted(self):
        """Worst case from the issue: a buffer as short as MIN_SAMPLES lands
        entirely inside the old [0, hop) ramp and used to come out as a
        0 -> ~0.5 fade instead of the true constant signal."""
        processor = self._make_processor()
        fft_size = processor.psychoacoustic_eq.fft_size
        short_len = 1024
        assert short_len < fft_size // 2
        audio = np.full(short_len, 0.7, dtype=np.float64)

        p1, p2 = self._patches()
        with p1, p2:
            result = processor._process_with_psychoacoustic_eq(audio, {})

        assert len(result) == short_len
        assert result[0] == pytest.approx(0.0, abs=1e-9)
        np.testing.assert_allclose(
            result[1:], np.full(short_len - 1, 0.7),
            atol=1e-6,
            err_msg="Short buffer entirely inside the old ramp region is still corrupted",
        )


@pytest.mark.regression
class TestEQWolaDtypePreservation:
    """The WOLA path must keep the buffer dtype (#4107).

    A float64 synthesis window promotes the overlap-add multiply to float64,
    which the in-place += into the float32 buffer truncates on every overlap
    step. The window is now cast to the buffer dtype so the accumulation stays
    in the input dtype.
    """

    def _make_processor(self, sample_rate=44100):
        settings = EQSettings(sample_rate=sample_rate, fft_size=4096)
        eq = PsychoacousticEQ(settings)
        return EQProcessor(eq)

    def _run(self, audio):
        """Run the WOLA path with identity EQ, capturing the dtype of each
        chunk handed to process_realtime_chunk."""
        seen: list = []

        def capture(self, chunk, target_curve, content_profile=None):
            seen.append(chunk.dtype)
            return chunk.copy()

        processor = self._make_processor()
        with patch.object(PsychoacousticEQ, 'process_realtime_chunk', capture), \
             patch.object(EQProcessor, '_eq_curve_to_array', _zero_curve):
            result = processor._process_with_psychoacoustic_eq(audio, {})
        return result, seen

    def test_float32_input_stays_float32_through_wola(self):
        n = self._make_processor().psychoacoustic_eq.fft_size * 4
        audio = np.random.RandomState(7).randn(n, 2).astype(np.float32)

        result, seen = self._run(audio)

        # Every chunk handed to the EQ is float32 (no float64 promotion).
        assert seen and all(dt == np.float32 for dt in seen)
        # Output preserves dtype and sample count (WOLA trim intact).
        assert result.dtype == np.float32
        assert len(result) == n

    def test_float64_input_stays_float64(self):
        n = self._make_processor().psychoacoustic_eq.fft_size * 4
        audio = np.random.RandomState(7).randn(n, 2).astype(np.float64)

        result, seen = self._run(audio)

        assert seen and all(dt == np.float64 for dt in seen)
        assert result.dtype == np.float64
        assert len(result) == n
