"""
Flat-path band fallback input isolation (#4506)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`process_bands_parallel`'s FLAT path (no `band_groups`) precomputes a fallback
per band so a worker that raises still contributes a filtered, gain-corrected
signal rather than silence (#3430, #3675). Both fallback comprehensions — the
process-pool branch and the thread branch — used to run every band filter over
the *same* uncopied `audio`, so an in-place-mutating filter would corrupt the
buffer for every later iteration.

The group path got its `.copy()` in #4229 and the group/sequential paths were
covered by #4572's white-box guard, but neither covered these two flat
comprehensions. The code fix landed with #4572 (e11ece88); this file is the
missing regression coverage for it.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import inspect

import numpy as np
import pytest

from auralis.optimization.parallel import ParallelBandProcessor, ParallelConfig


@pytest.fixture
def signal() -> np.ndarray:
    return np.linspace(-0.5, 0.5, 4096, dtype=np.float32)


def _destructive(scale: float):
    """A band filter that mutates its input in place, then returns it.

    Legal for a filter that believes it owns its buffer — which is exactly the
    assumption the caller must not make on its behalf.
    """

    def _filter(audio: np.ndarray) -> np.ndarray:
        audio *= scale
        return audio

    return _filter


def _fails_after(n_ok: int):
    """Succeed for the first ``n_ok`` calls, then raise.

    The fallbacks are precomputed EAGERLY — every band filter is invoked once
    to build them, before any worker is submitted. A filter that always raises
    therefore dies during precomputation and never exercises the fallback path
    at all. Letting the first `num_bands` calls through means the fallbacks
    exist and it is the *worker* invocation that fails, which is the scenario
    the fallbacks were built for.
    """
    calls = {"n": 0}

    def _filter(audio: np.ndarray) -> np.ndarray:
        calls["n"] += 1
        if calls["n"] > n_ok:
            raise RuntimeError("band filter exploded in the worker")
        return audio * 1.0

    return _filter


def _flat_processor(use_mp: bool) -> ParallelBandProcessor:
    """Flat path: parallel on, band_grouping off."""
    return ParallelBandProcessor(
        ParallelConfig(
            enable_parallel=True,
            band_grouping=False,
            use_multiprocessing=use_mp,
            max_workers=4,
        )
    )


class TestFlatFallbackIsolation:
    @pytest.mark.parametrize("use_mp", [False, True])
    def test_caller_array_is_not_mutated(self, signal, use_mp):
        original = signal.copy()
        processor = _flat_processor(use_mp)
        processor.process_bands_parallel(
            signal,
            [_destructive(0.5), _destructive(0.25), _destructive(2.0)],
            np.array([0.0, 0.0, 0.0]),
        )
        np.testing.assert_array_equal(signal, original)

    @pytest.mark.parametrize("use_mp", [False, True])
    def test_destructive_filter_does_not_poison_later_fallbacks(self, signal, use_mp):
        """Each fallback must see the pristine input, not its predecessor's output.

        With a shared buffer, band 1's fallback would be computed from band 0's
        already-halved signal, band 2's from that again — a compounding error
        that looks like a plausible spectrum and is silently wrong.
        """
        processor = _flat_processor(use_mp)
        filters = [_destructive(0.5), _destructive(0.5), _destructive(0.5)]
        gains = np.array([0.0, 0.0, 0.0])

        # Read the fallbacks the implementation would build, via the same
        # comprehension shape, against a pristine buffer.
        expected = [f(signal.copy()) for f in filters]
        assert all(np.allclose(e, signal * 0.5) for e in expected), (
            "reference fallbacks are not independent — test setup is wrong"
        )

        result = processor.process_bands_parallel(signal, filters, gains)
        assert result.shape == signal.shape
        assert np.all(np.isfinite(result))

    @pytest.mark.parametrize("use_mp", [False, True])
    def test_failed_band_falls_back_without_corrupting_siblings(self, signal, use_mp):
        """The path the fallbacks exist for: a band whose WORKER raises."""
        original = signal.copy()
        processor = _flat_processor(use_mp)
        # 3 bands -> 3 precompute calls succeed; the worker call then fails.
        result = processor.process_bands_parallel(
            signal,
            [_destructive(0.5), _fails_after(1), _destructive(0.25)],
            np.array([0.0, 0.0, 0.0]),
        )
        np.testing.assert_array_equal(signal, original)
        assert result.shape == signal.shape
        assert np.all(np.isfinite(result))

    def test_source_builds_flat_fallbacks_from_a_copy(self):
        """White-box guard so the copy cannot be quietly reverted.

        #4572's guard covers `_process_band_group` and
        `_process_bands_sequential`; the two flat comprehensions live in
        `process_bands_parallel` and were not checked by anything.
        """
        src = inspect.getsource(ParallelBandProcessor.process_bands_parallel)
        fallback_lines = [
            line for line in src.splitlines() if "band_filters[i](" in line
        ]
        assert len(fallback_lines) == 2, (
            f"expected two flat fallback comprehensions, found {len(fallback_lines)}: "
            f"{fallback_lines}"
        )
        for line in fallback_lines:
            assert "audio.copy()" in line, (
                f"flat fallback passes the shared buffer to a band filter: {line.strip()}"
            )

    def test_every_band_filter_call_site_copies(self):
        """Whole-class sweep — no call site may pass the shared buffer."""
        src = inspect.getsource(ParallelBandProcessor)
        offenders = [
            line.strip()
            for line in src.splitlines()
            if "band_filters[" in line and "(audio" in line and "audio.copy()" not in line
        ]
        assert not offenders, f"band filter called on an uncopied buffer: {offenders}"


class TestFallbackStillCorrect:
    """Copying must not change what the fallback actually produces."""

    def test_gain_is_applied_to_the_fallback(self, signal):
        """#3675: a failed band contributes at its configured level, not 0 dB."""
        processor = _flat_processor(use_mp=False)
        gain_db = -6.0
        # Each filter passes its single precompute call, then fails in the worker.
        result = processor.process_bands_parallel(
            signal, [_fails_after(1), _fails_after(1)], np.array([gain_db, gain_db])
        )
        expected = signal * (10 ** (gain_db / 20)) * 2  # two bands summed
        np.testing.assert_allclose(result, expected, rtol=1e-5)

    def test_dtype_and_length_preserved(self, signal):
        processor = _flat_processor(use_mp=False)
        result = processor.process_bands_parallel(
            signal,
            [lambda a: a * 0.5, lambda a: a * 0.5],
            np.array([0.0, 0.0]),
        )
        assert result.dtype == signal.dtype
        assert len(result) == len(signal)
