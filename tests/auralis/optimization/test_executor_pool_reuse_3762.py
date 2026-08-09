"""
Regression tests for #3762 — parallel paths must reuse their executors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every parallel entry point used to open a `with ThreadPoolExecutor(...)` /
`with ProcessPoolExecutor(...)` block per call, so each call paid full worker
startup (~50-100 ms per process on Linux, 500-1000 ms on Windows) and then tore
the workers down again. The fix caches one executor per (kind, max_workers) in
an `ExecutorPool` owned by each processor.

These tests assert the *identity* of the executor across calls rather than
timing, so they are deterministic and fast.
"""

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import numpy as np
import pytest

from auralis.optimization.parallel import (
    ExecutorPool,
    ParallelAudioProcessor,
    ParallelBandProcessor,
    ParallelConfig,
    ParallelFeatureExtractor,
    ParallelFFTProcessor,
)


def _identity(audio: np.ndarray) -> np.ndarray:
    """Module-level (picklable) no-op processing function."""
    return audio


class TestExecutorPool:
    """Unit tests for the ExecutorPool primitive itself."""

    def test_get_returns_same_executor_for_same_key(self):
        pool = ExecutorPool("test")
        try:
            first = pool.get(4)
            second = pool.get(4)
            assert first is second
            assert isinstance(first, ThreadPoolExecutor)
        finally:
            pool.close()

    def test_distinct_keys_get_distinct_executors(self):
        pool = ExecutorPool("test")
        try:
            assert pool.get(2) is not pool.get(4)
        finally:
            pool.close()

    def test_process_and_thread_pools_do_not_alias(self):
        pool = ExecutorPool("test")
        try:
            threaded = pool.get(2, use_multiprocessing=False)
            processed = pool.get(2, use_multiprocessing=True)
            assert threaded is not processed
            assert isinstance(threaded, ThreadPoolExecutor)
            assert isinstance(processed, ProcessPoolExecutor)
        finally:
            pool.close()

    def test_close_is_idempotent_and_pool_stays_usable(self):
        pool = ExecutorPool("test")
        first = pool.get(2)
        pool.close()
        pool.close()  # must not raise

        # A closed pool rebuilds on demand rather than raising.
        second = pool.get(2)
        try:
            assert second is not first
            assert second.submit(int, "7").result() == 7
        finally:
            pool.close()

    def test_shut_down_executor_is_replaced(self):
        """An externally shut-down executor must not be handed out again."""
        pool = ExecutorPool("test")
        try:
            stale = pool.get(2)
            stale.shutdown(wait=True)

            fresh = pool.get(2)
            assert fresh is not stale
            assert fresh.submit(int, "1").result() == 1
        finally:
            pool.close()


class TestProcessorsReuseTheirPool:
    """Each parallel entry point must reuse workers across repeated calls."""

    def test_process_batch_reuses_one_executor(self):
        processor = ParallelAudioProcessor(ParallelConfig(max_workers=2))
        try:
            batch = [np.zeros(8, dtype=np.float32) for _ in range(3)]

            processor.process_batch(batch, _identity)
            after_first = dict(processor._executor_pool._executors)
            assert len(after_first) == 1

            # A differently-sized batch must not build a second pool — the pool
            # is keyed on the configured ceiling, not on len(audio_files).
            processor.process_batch(batch * 4, _identity)
            after_second = dict(processor._executor_pool._executors)

            assert list(after_second.values()) == list(after_first.values())
        finally:
            processor.close()

    def test_band_processing_reuses_one_executor(self):
        processor = ParallelBandProcessor(
            ParallelConfig(max_workers=2, band_grouping=False)
        )
        try:
            audio = np.ones(64, dtype=np.float32)
            filters = [lambda a: a, lambda a: a * 0.5, lambda a: a * 0.25]
            gains = np.zeros(3)

            processor.process_bands_parallel(audio, filters, gains)
            executors = list(processor._executor_pool._executors.values())
            assert len(executors) == 1

            processor.process_bands_parallel(audio, filters[:2], gains[:2])
            assert list(processor._executor_pool._executors.values()) == executors
        finally:
            processor.close()

    def test_band_group_processing_reuses_the_same_pool(self):
        """Grouped and ungrouped band paths share one thread pool."""
        processor = ParallelBandProcessor(
            ParallelConfig(max_workers=2, band_grouping=True)
        )
        try:
            audio = np.ones(64, dtype=np.float32)
            filters = [lambda a: a, lambda a: a * 0.5, lambda a: a * 0.25, lambda a: a]
            gains = np.zeros(4)

            processor.process_bands_parallel(audio, filters, gains, [[0, 1], [2, 3]])
            processor.process_bands_parallel(audio, filters, gains, [[0], [1], [2], [3]])

            assert len(processor._executor_pool._executors) == 1
        finally:
            processor.close()

    def test_windowed_fft_reuses_one_executor(self):
        processor = ParallelFFTProcessor(ParallelConfig(max_workers=2))
        try:
            audio = np.random.RandomState(0).randn(4096).astype(np.float32)

            processor.parallel_windowed_fft(audio, fft_size=512)
            executors = list(processor._executor_pool._executors.values())
            assert len(executors) == 1

            # Half the audio => half the chunks; still the same pool.
            processor.parallel_windowed_fft(audio[:2048], fft_size=512)
            assert list(processor._executor_pool._executors.values()) == executors
        finally:
            processor.close()

    def test_feature_extraction_reuses_one_executor(self):
        extractor = ParallelFeatureExtractor(ParallelConfig(max_workers=2))
        try:
            audio = np.ones(32, dtype=np.float32)
            extractors = {
                "mean": lambda a: float(np.mean(a)),
                "peak": lambda a: float(np.max(np.abs(a))),
                "rms": lambda a: float(np.sqrt(np.mean(a ** 2))),
            }

            first = extractor.extract_features_parallel(audio, extractors)
            executors = list(extractor._executor_pool._executors.values())
            assert len(executors) == 1
            assert first["mean"] == pytest.approx(1.0)

            extractor.extract_features_parallel(audio, dict(list(extractors.items())[:2]))
            assert list(extractor._executor_pool._executors.values()) == executors
        finally:
            extractor.close()


class TestCloseLifecycle:
    """close() must release every pool the processor tree owns (ENG-6 parity)."""

    def test_audio_processor_close_releases_subprocessor_pools(self):
        processor = ParallelAudioProcessor(ParallelConfig(max_workers=2))

        processor.process_batch(
            [np.zeros(8, dtype=np.float32) for _ in range(3)], _identity
        )
        processor.feature_extractor.extract_features_parallel(
            np.ones(16, dtype=np.float32),
            {"mean": lambda a: float(np.mean(a)), "peak": lambda a: float(np.max(a))},
        )
        assert processor._executor_pool._executors
        assert processor.feature_extractor._executor_pool._executors

        processor.close()

        assert processor._executor_pool._executors == {}
        assert processor.fft_processor._executor_pool._executors == {}
        assert processor.band_processor._executor_pool._executors == {}
        assert processor.feature_extractor._executor_pool._executors == {}

    def test_processor_still_works_after_close(self):
        processor = ParallelAudioProcessor(ParallelConfig(max_workers=2))
        try:
            batch = [np.arange(4, dtype=np.float32) for _ in range(3)]
            processor.process_batch(batch, _identity)
            processor.close()

            results = processor.process_batch(batch, _identity)
            assert len(results) == 3
            assert all(r is not None for r in results)
        finally:
            processor.close()


class TestPoolingPreservesResults:
    """Pooling is a lifecycle change only — outputs must be unchanged."""

    def test_repeated_batches_return_correct_results(self):
        processor = ParallelAudioProcessor(ParallelConfig(max_workers=3))
        try:
            batch = [np.full(8, i, dtype=np.float32) for i in range(5)]
            for _ in range(3):
                results = processor.process_batch(batch, _identity)
                assert len(results) == len(batch)
                for expected, actual in zip(batch, results):
                    assert actual is not None
                    np.testing.assert_array_equal(actual, expected)
        finally:
            processor.close()

    def test_repeated_band_processing_is_stable(self):
        processor = ParallelBandProcessor(
            ParallelConfig(max_workers=2, band_grouping=False)
        )
        try:
            audio = np.linspace(-1.0, 1.0, 128, dtype=np.float32)
            filters = [lambda a: a * 0.5, lambda a: a * 0.5]
            gains = np.zeros(2)

            first = processor.process_bands_parallel(audio, filters, gains)
            second = processor.process_bands_parallel(audio, filters, gains)

            np.testing.assert_array_equal(first, second)
            np.testing.assert_allclose(first, audio, atol=1e-6)
            assert first.dtype == audio.dtype
            assert len(first) == len(audio)
        finally:
            processor.close()
