"""
Input isolation in the parallel DSP helpers (#4572, #4573)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two hardening gaps in `auralis/optimization/parallel/`:

- **#4572**: `_process_band_group()` passed the *same* un-copied array to every
  band filter in a group, so an in-place filter corrupted the input for the
  remaining bands. Cross-*worker* copying was already handled (#3355) and the
  exception-fallback path got the per-band copy in #4229 — with a comment
  saying "like the worker path", while the worker path itself did not copy.

- **#4573**: `get_window()` handed out a directly-writable reference to the
  shared, cross-thread window cache. `parallel_windowed_fft` froze it at one
  call site (#3761), leaving the sub-FFT-size early return and every external
  caller of the public `get_window()` unprotected.

NOTE: `auralis/optimization/parallel/` has **no production importers** — only
tests reach it, via the `auralis.optimization.parallel_processor` shim. Both
fixes are unobservable at the application level; they exist so the bug class
cannot return if the package is ever wired up.
"""

import inspect

import numpy as np
import pytest

from auralis.optimization.parallel.band_processor import ParallelBandProcessor
from auralis.optimization.parallel.fft_processor import ParallelFFTProcessor


def _destructive_filter(audio: np.ndarray) -> np.ndarray:
    """A band filter that mutates its input in place, then returns it."""
    audio *= 0.0
    return audio


def _passthrough(audio: np.ndarray) -> np.ndarray:
    return audio


@pytest.fixture
def signal() -> np.ndarray:
    return np.linspace(0.1, 1.0, 256).astype(np.float32)


class TestBandGroupInputIsolation:
    """#4572 — one in-place filter must not poison its group-mates."""

    def test_destructive_filter_does_not_corrupt_later_bands(self, signal):
        processor = ParallelBandProcessor()
        gains = np.array([0.0, 0.0])

        result = processor._process_band_group(
            signal, [_destructive_filter, _passthrough], gains, [0, 1]
        )

        # Band 0 contributes silence, band 1 must contribute the pristine input.
        np.testing.assert_allclose(result, signal, rtol=1e-6)

    def test_caller_array_is_not_mutated(self, signal):
        processor = ParallelBandProcessor()
        original = signal.copy()

        processor._process_band_group(
            signal, [_destructive_filter], np.array([0.0]), [0]
        )

        np.testing.assert_array_equal(signal, original)

    def test_sequential_path_is_isolated_too(self, signal):
        processor = ParallelBandProcessor()

        result = processor._process_bands_sequential(
            signal, [_destructive_filter, _passthrough], np.array([0.0, 0.0])
        )

        np.testing.assert_allclose(result, signal, rtol=1e-6)

    def test_group_result_preserves_dtype_and_length(self, signal):
        """The copy must not disturb the #4125 dtype contract."""
        processor = ParallelBandProcessor()

        result = processor._process_band_group(
            signal, [_passthrough, _passthrough], np.array([0.0, 0.0]), [0, 1]
        )

        assert result.dtype == signal.dtype
        assert len(result) == len(signal)

    @pytest.mark.parametrize(
        "method", ["_process_band_group", "_process_bands_sequential"]
    )
    def test_source_calls_filters_with_a_copy(self, method):
        """White-box guard so the copy cannot be quietly reverted (#4572)."""
        src = inspect.getsource(getattr(ParallelBandProcessor, method))
        assert "(audio.copy())" in src, (
            f"{method} must pass a copy to each band filter — an in-place "
            f"filter would otherwise corrupt the input for the remaining bands"
        )


class TestWindowCacheIsReadOnly:
    """#4573 — the guard belongs at the source, not at one call site."""

    @pytest.mark.parametrize("size", [512, 1024, 2048, 4096, 8192])
    def test_prewarmed_windows_are_frozen(self, size):
        processor = ParallelFFTProcessor()

        assert processor.get_window(size).flags.writeable is False

    def test_computed_on_demand_window_is_frozen(self):
        """The slow path populates the cache too — it must freeze as well."""
        processor = ParallelFFTProcessor()

        assert processor.get_window(777).flags.writeable is False
        # And the cached object itself, not just the returned reference.
        assert processor.window_cache[777].flags.writeable is False

    def test_writing_to_a_window_raises(self):
        processor = ParallelFFTProcessor()
        window = processor.get_window(4096)

        with pytest.raises(ValueError):
            window[0] = 1.0

    def test_sub_fft_size_path_receives_a_readonly_window(self):
        """The #3439 early return bypassed the old call-site guard entirely."""
        processor = ParallelFFTProcessor()
        seen: list[bool] = []
        original = processor._process_fft_chunk

        def spy(chunk, window, fft_size):
            seen.append(window.flags.writeable)
            return original(chunk, window, fft_size)

        processor._process_fft_chunk = spy  # type: ignore[method-assign]
        processor.parallel_windowed_fft(np.zeros(128, dtype=np.float32), fft_size=4096)

        assert seen == [False]

    def test_caller_supplied_window_is_left_alone(self):
        """A caller's own array bypasses the cache and stays writable."""
        processor = ParallelFFTProcessor()
        own = np.hanning(4096).astype(np.float64)
        seen: list[bool] = []
        original = processor._process_fft_chunk

        def spy(chunk, window, fft_size):
            seen.append(window.flags.writeable)
            return original(chunk, window, fft_size)

        processor._process_fft_chunk = spy  # type: ignore[method-assign]
        processor.parallel_windowed_fft(
            np.zeros(128, dtype=np.float32), fft_size=4096, window=own
        )

        assert seen == [True]
        assert own.flags.writeable is True

    def test_redundant_call_site_setflags_removed(self):
        """Leaving both guards suggests the source one is optional (#4573)."""
        src = inspect.getsource(ParallelFFTProcessor.parallel_windowed_fft)
        assert "setflags(write=False)" not in src

    def test_multi_frame_path_still_produces_frames(self):
        """Removing the per-call view must not change FFT behaviour."""
        processor = ParallelFFTProcessor()
        audio = np.random.default_rng(0).standard_normal(8192).astype(np.float32)

        frames = processor.parallel_windowed_fft(audio, fft_size=1024)

        assert len(frames) > 1
        assert all(isinstance(f, np.ndarray) for f in frames)
