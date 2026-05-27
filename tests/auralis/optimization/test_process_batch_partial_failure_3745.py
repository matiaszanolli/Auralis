"""
Regression tests for #3745 — ParallelAudioProcessor.process_batch must
not abort the entire batch on a single file's failure.

Pre-fix the method used `executor.map(process_func, audio_files)` and
drained via `list(...)`. `executor.map` re-raises the first exception
encountered, so a single bad file in a batch raised immediately and
the rest of the results were discarded.

Post-fix uses `submit` + `as_completed` with a per-future try/except,
matching the canonical pattern from `ParallelBandProcessor` (#3430).
Failed entries land as `None` in the returned list at the original
index; callers iterate and treat `None` as "this file failed".
"""

from __future__ import annotations

import numpy as np

from auralis.optimization.parallel_processor import (
    ParallelAudioProcessor,
    ParallelConfig,
)


def _identity(audio: np.ndarray) -> np.ndarray:
    return audio


def _raise_on_marker(audio: np.ndarray) -> np.ndarray:
    """Raise iff the audio array's first sample is exactly -1.0 — used as a
    deterministic marker in the test inputs."""
    if audio.size > 0 and audio[0] == -1.0:
        raise RuntimeError("simulated per-file failure")
    return audio


class TestProcessBatchPartialFailure:
    def _make_processor(self, multiprocessing: bool = False) -> ParallelAudioProcessor:
        config = ParallelConfig(
            max_workers=2,
            enable_parallel=True,
            use_multiprocessing=multiprocessing,
        )
        return ParallelAudioProcessor(config)

    def test_threading_path_returns_partial_results_on_one_failure(self) -> None:
        proc = self._make_processor(multiprocessing=False)
        good_a = np.full(8, 0.5, dtype=np.float32)
        bad = np.array([-1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        good_b = np.full(8, 0.25, dtype=np.float32)

        results = proc.process_batch(
            [good_a, bad, good_b], _raise_on_marker
        )

        assert len(results) == 3
        # Good entries arrive in input order.
        assert results[0] is not None and np.array_equal(results[0], good_a)
        assert results[2] is not None and np.array_equal(results[2], good_b)
        # Failed entry is None.
        assert results[1] is None

    def test_threading_path_all_failures_returns_all_none(self) -> None:
        proc = self._make_processor(multiprocessing=False)
        bad_a = np.array([-1.0, 0.0], dtype=np.float32)
        bad_b = np.array([-1.0, 0.0], dtype=np.float32)
        bad_c = np.array([-1.0, 0.0], dtype=np.float32)

        results = proc.process_batch([bad_a, bad_b, bad_c], _raise_on_marker)

        assert results == [None, None, None]

    def test_threading_path_zero_failures_returns_all_results(self) -> None:
        proc = self._make_processor(multiprocessing=False)
        items = [np.full(8, float(i), dtype=np.float32) for i in range(5)]

        results = proc.process_batch(items, _identity)

        assert len(results) == 5
        for i, r in enumerate(results):
            assert r is not None
            assert float(r[0]) == float(i)

    def test_sequential_fallback_preserves_raise_semantics(self) -> None:
        """The sequential fallback (enable_parallel=False or <2 items) is
        deliberately untouched — caller can wrap in try/except if they
        want the same per-file isolation. Pin that contract."""
        config = ParallelConfig(
            max_workers=2,
            enable_parallel=False,
            use_multiprocessing=False,
        )
        proc = ParallelAudioProcessor(config)
        bad = np.array([-1.0, 0.0], dtype=np.float32)

        try:
            proc.process_batch([bad, bad], _raise_on_marker)
        except RuntimeError as exc:
            assert "simulated per-file failure" in str(exc)
        else:
            raise AssertionError("expected RuntimeError on sequential path")
