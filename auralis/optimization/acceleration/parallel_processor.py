"""
Parallel Processor
~~~~~~~~~~~~~~~~~~

Parallel processing framework for CPU-intensive operations.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor
from typing import cast
from collections.abc import Callable

import numpy as np

from auralis.utils.logging import debug


class ParallelProcessor:
    """Parallel processing for CPU-intensive operations"""

    def __init__(self, max_threads: int | None = None) -> None:
        self.max_threads = max_threads or min(4, mp.cpu_count())
        self.executor = ThreadPoolExecutor(max_workers=self.max_threads)
        debug(f"Parallel processor initialized with {self.max_threads} threads")

    def parallel_band_processing(self, audio: np.ndarray,
                                band_filters: list[Callable[[np.ndarray], np.ndarray]],
                                band_gains: np.ndarray) -> np.ndarray:
        """Process frequency bands in parallel"""
        if len(band_filters) < 2:
            # Not worth parallelizing
            return self._sequential_band_processing(audio, band_filters, band_gains)

        # Submit band processing tasks
        futures = []
        for i, (band_filter, gain) in enumerate(zip(band_filters, band_gains)):
            future = self.executor.submit(self._process_single_band, audio, band_filter, float(gain))
            futures.append(future)

        # Collect results and sum
        result = np.zeros_like(audio)
        for future in futures:
            band_result = future.result()
            result += band_result

        return result

    def _process_single_band(self, audio: np.ndarray,
                           band_filter: Callable[[np.ndarray], np.ndarray], gain: float) -> np.ndarray:
        """Process a single frequency band"""
        filtered = band_filter(audio)
        return cast(np.ndarray, filtered * gain)

    def _sequential_band_processing(self, audio: np.ndarray,
                                  band_filters: list[Callable[[np.ndarray], np.ndarray]],
                                  band_gains: np.ndarray) -> np.ndarray:
        """Sequential fallback for band processing"""
        result = np.zeros_like(audio)
        for band_filter, gain in zip(band_filters, band_gains):
            filtered = band_filter(audio)
            result += filtered * float(gain)
        return result

    def shutdown(self) -> None:
        """Shutdown thread pool"""
        self.executor.shutdown(wait=True)
