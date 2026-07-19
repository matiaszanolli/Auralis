"""
Parallel Audio Processor
~~~~~~~~~~~~~~~~~~~~~~~~~

Main orchestrator composing the FFT / band / feature sub-processors, plus the
global-instance accessors (#4276).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Any
from collections.abc import Callable

import numpy as np

from ...utils.logging import debug, info, warning
from .band_processor import ParallelBandProcessor
from .config import ParallelConfig
from .feature_extractor import ParallelFeatureExtractor
from .fft_processor import ParallelFFTProcessor


class ParallelAudioProcessor:
    """Main parallel audio processing orchestrator"""

    def __init__(self, config: ParallelConfig | None = None) -> None:
        self.config: ParallelConfig = config or ParallelConfig()

        # Initialize sub-processors
        self.fft_processor: ParallelFFTProcessor = ParallelFFTProcessor(config)
        self.band_processor: ParallelBandProcessor = ParallelBandProcessor(config)
        self.feature_extractor: ParallelFeatureExtractor = ParallelFeatureExtractor(config)

        info(f"Parallel audio processor initialized with {self.config.max_workers} workers")

    def process_batch(
        self,
        audio_files: list[np.ndarray],
        process_func: Callable[[np.ndarray], np.ndarray],
        max_workers: int | None = None
    ) -> list[np.ndarray | None]:
        """
        Process multiple audio files in parallel.

        #3745: per-file error handling. The previous implementation used
        `executor.map(...)` and drained via `list(...)` — `executor.map`
        re-raises the first exception, so a single bad file in a batch of
        100 raised immediately and the other 99 results were discarded.
        Matches the canonical pattern from `ParallelBandProcessor`
        (#3430): submit + `as_completed` with a per-future try/except.

        Args:
            audio_files: List of audio arrays
            process_func: Processing function to apply to each file
            max_workers: Override default max workers

        Returns:
            List of processed audio arrays, in input order. Entries for
            files that raised during processing are `None` (with the
            exception logged via `warning()`). Callers iterating the
            result should treat `None` as "this file failed".
        """
        if not self.config.enable_parallel or len(audio_files) < 2:
            # Sequential processing — keep the original raise-on-error
            # semantics for the in-process path; the caller can wrap in
            # try/except if they want the same per-file isolation.
            return [process_func(audio) for audio in audio_files]

        num_workers = max_workers or min(self.config.max_workers, len(audio_files))

        # Use multiprocessing for batch processing (true parallelism);
        # threading fallback otherwise. Both share the same
        # submit + as_completed + per-future try/except plumbing.
        ExecutorCls = (
            ProcessPoolExecutor if self.config.use_multiprocessing
            else ThreadPoolExecutor
        )
        results: list[np.ndarray | None] = [None] * len(audio_files)
        with ExecutorCls(max_workers=num_workers) as executor:
            future_to_index = {
                executor.submit(process_func, audio): idx
                for idx, audio in enumerate(audio_files)
            }
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:  # noqa: BLE001
                    warning(
                        f"process_batch: file at index {idx} failed: {exc}"
                    )
                    # results[idx] stays None — caller handles partial batch.

        return results

    def get_config(self) -> ParallelConfig:
        """Get current configuration"""
        return self.config

    def update_config(self, **kwargs: Any) -> None:
        """Update configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                debug(f"Updated config: {key}={value}")


# Global parallel processor instance and its creation lock (#2314)
_global_parallel_processor: ParallelAudioProcessor | None = None
_global_parallel_processor_lock: threading.Lock = threading.Lock()


def get_parallel_processor(config: ParallelConfig | None = None) -> ParallelAudioProcessor:
    """Get global parallel processor instance.

    Uses a double-check pattern: a fast unlocked read avoids lock overhead on
    the common hot path; the lock + inner check closes the TOCTOU window for
    the first call (fixes #2314).
    """
    global _global_parallel_processor
    if _global_parallel_processor is not None:
        return _global_parallel_processor
    with _global_parallel_processor_lock:
        if _global_parallel_processor is None:
            _global_parallel_processor = ParallelAudioProcessor(config)
        return _global_parallel_processor


def create_parallel_processor(config: ParallelConfig | None = None) -> ParallelAudioProcessor:
    """Create new parallel processor instance"""
    return ParallelAudioProcessor(config)
