"""
Regression tests for the oversized-chunk truncation in ParallelEQProcessor —
issue #4507.

`apply_eq_gains_parallel` only handled `len < fft_size` (zero-pad). For
`len > fft_size`, both mono paths did `fft(audio_mono[:fft_size])`, so the
IFFT produced only `fft_size` samples. Neither the mono return slice
(`processed_audio[:len(audio_mono)]`) nor the caller's
`result[:original_length]` could restore the dropped tail — both slice to the
smaller of the two — so the output silently collapsed to `fft_size` samples:
a sample-count violation.

The fix matches the contract its two siblings already enforce under #3742
(`filters.apply_eq_mono` and `VectorizedEQProcessor._apply_eq_mono_vectorized`):
fail loud with a ValueError telling the caller to chunk at `fft_size`, rather
than block-process. `ParallelEQProcessor` was the only one of the three
missing it.

Acceptance criteria:
  - len > fft_size raises ValueError on BOTH the parallel and sequential mono
    paths, mono and stereo, instead of returning a short buffer
  - len == fft_size and len < fft_size still preserve sample count exactly
  - parallel and sequential paths agree at len == fft_size

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.dsp.eq.parallel_eq_processor import ParallelEQConfig, ParallelEQProcessor

SAMPLE_RATE = 44100
FFT_SIZE = 4096
N_BANDS = 26


def _band_map(fft_size: int = FFT_SIZE, n_bands: int = N_BANDS) -> np.ndarray:
    """Distribute FFT bins evenly across n_bands."""
    num_bins = fft_size // 2 + 1
    band_map = np.zeros(num_bins, dtype=int)
    bins_per_band = num_bins // n_bands
    for b in range(n_bands):
        band_map[b * bins_per_band:(b + 1) * bins_per_band] = b
    band_map[(n_bands - 1) * bins_per_band:] = n_bands - 1
    return band_map


def _sine(n_samples: int) -> np.ndarray:
    t = np.arange(n_samples) / SAMPLE_RATE
    return np.sin(2 * np.pi * 1000.0 * t).astype(np.float64)


def _gains() -> np.ndarray:
    return np.full(N_BANDS, 3.0)


def _parallel() -> ParallelEQProcessor:
    return ParallelEQProcessor(ParallelEQConfig(
        enable_parallel=True,
        use_band_grouping=True,
        min_bands_for_parallel=8,
    ))


def _sequential() -> ParallelEQProcessor:
    return ParallelEQProcessor(ParallelEQConfig(enable_parallel=False))


class TestOversizedChunkRejected:
    """len > fft_size must fail loud, not silently truncate (#4507)."""

    @pytest.mark.parametrize("processor_factory", [_parallel, _sequential])
    @pytest.mark.parametrize("overshoot", [1, 1000, FFT_SIZE])
    def test_mono_longer_than_fft_size_raises(self, processor_factory, overshoot):
        processor = processor_factory()
        audio = _sine(FFT_SIZE + overshoot)

        with pytest.raises(ValueError, match="exceeds fft_size"):
            processor.apply_eq_gains_parallel(audio, _gains(), _band_map(), FFT_SIZE)

    @pytest.mark.parametrize("processor_factory", [_parallel, _sequential])
    def test_stereo_longer_than_fft_size_raises(self, processor_factory):
        """The stereo path fans out to the mono path via a thread pool; the
        ValueError must propagate through `future.result()`, not be swallowed."""
        processor = processor_factory()
        mono = _sine(FFT_SIZE + 500)
        stereo = np.column_stack([mono, mono * 0.5])

        with pytest.raises(ValueError, match="exceeds fft_size"):
            processor.apply_eq_gains_parallel(stereo, _gains(), _band_map(), FFT_SIZE)

    @pytest.mark.parametrize("processor_factory", [_parallel, _sequential])
    def test_error_names_the_offending_lengths(self, processor_factory):
        """The message must be actionable — both lengths and the remedy."""
        processor = processor_factory()
        audio = _sine(FFT_SIZE + 777)

        with pytest.raises(ValueError) as excinfo:
            processor.apply_eq_gains_parallel(audio, _gains(), _band_map(), FFT_SIZE)

        message = str(excinfo.value)
        assert str(FFT_SIZE + 777) in message
        assert str(FFT_SIZE) in message
        assert "chunk at fft_size" in message


class TestSupportedLengthsPreserveSampleCount:
    """The lengths that ARE supported must still round-trip exactly."""

    @pytest.mark.parametrize("processor_factory", [_parallel, _sequential])
    @pytest.mark.parametrize("length", [FFT_SIZE, FFT_SIZE - 1, FFT_SIZE // 2, 1])
    def test_mono_sample_count_preserved(self, processor_factory, length):
        processor = processor_factory()
        audio = _sine(length)

        result = processor.apply_eq_gains_parallel(
            audio, _gains(), _band_map(), FFT_SIZE
        )

        assert len(result) == length
        assert isinstance(result, np.ndarray)

    @pytest.mark.parametrize("processor_factory", [_parallel, _sequential])
    @pytest.mark.parametrize("length", [FFT_SIZE, FFT_SIZE - 1, FFT_SIZE // 2])
    def test_stereo_sample_count_preserved(self, processor_factory, length):
        processor = processor_factory()
        mono = _sine(length)
        stereo = np.column_stack([mono, mono * 0.5])

        result = processor.apply_eq_gains_parallel(
            stereo, _gains(), _band_map(), FFT_SIZE
        )

        assert result.shape == (length, 2)

    def test_parallel_and_sequential_agree_at_fft_size(self):
        """Both guarded paths must still produce the same output (#4507 test plan)."""
        audio = _sine(FFT_SIZE)

        out_parallel = _parallel().apply_eq_gains_parallel(
            audio, _gains(), _band_map(), FFT_SIZE
        )
        out_sequential = _sequential().apply_eq_gains_parallel(
            audio, _gains(), _band_map(), FFT_SIZE
        )

        np.testing.assert_allclose(out_parallel, out_sequential, rtol=1e-9, atol=1e-12)


class TestGuardMatchesSiblings:
    """The three EQ mono paths must enforce one shared contract (#3742/#4507)."""

    def test_vectorized_sibling_rejects_the_same_input(self):
        from auralis.dsp.eq.parallel_eq_processor import VectorizedEQProcessor

        audio = _sine(FFT_SIZE + 100)

        with pytest.raises(ValueError, match="exceeds fft_size"):
            VectorizedEQProcessor().apply_eq_gains_vectorized(
                audio, _gains(), _band_map(), FFT_SIZE
            )

    def test_filters_sibling_rejects_the_same_input(self):
        from auralis.dsp.eq.filters import apply_eq_mono

        audio = _sine(FFT_SIZE + 100)

        with pytest.raises(ValueError, match="exceeds"):
            apply_eq_mono(audio, _gains(), _band_map(), FFT_SIZE)
