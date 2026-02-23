"""
Parallel Processing Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~

High-performance parallel processing for audio DSP operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import wraps
from multiprocessing import cpu_count
from typing import Any
from collections.abc import Callable

import numpy as np

from ..utils.logging import debug, info


@dataclass
class ParallelConfig:
    """Configuration for parallel processing"""
    enable_parallel: bool = True
    max_workers: int = min(8, cpu_count())
    use_multiprocessing: bool = False  # False = threading, True = multiprocessing
    chunk_processing_threshold: int = 44100  # Min samples for parallel processing
    band_grouping: bool = True  # Group similar frequency bands
    shared_memory_threshold_mb: int = 10  # Use shared memory for arrays > this size
    adaptive_workers: bool = True  # Adjust workers based on chunk size


class ParallelFFTProcessor:
    """Parallel FFT processing for spectrum analysis"""

    def __init__(self, config: ParallelConfig | None = None) -> None:
        self.config: ParallelConfig = config or ParallelConfig()
        self.fft_plan_cache: dict[int, Any] = {}  # Cache FFT plans/windows for common sizes
        self.lock: threading.Lock = threading.Lock()
        self.window_cache: dict[int, np.ndarray] = {}

        # Pre-compute common window functions
        self._init_window_cache()

        debug(f"Parallel FFT processor initialized: max_workers={self.config.max_workers}")

    def _init_window_cache(self) -> None:
        """Pre-compute common window functions"""
        common_sizes: list[int] = [512, 1024, 2048, 4096, 8192]

        for size in common_sizes:
            self.window_cache[size] = np.hann(size)
            debug(f"Cached Hanning window for size {size}")

    def get_window(self, size: int) -> np.ndarray:
        """Get window function (cached or compute).

        Uses a double-check pattern so that np.hann() — which can be
        expensive for large sizes — is computed outside the lock, preventing
        all parallel threads from serialising on the first cache miss (#2077).
        """
        # Fast path: common sizes are pre-warmed in __init__, no lock needed.
        if size in self.window_cache:
            return self.window_cache[size]

        # Slow path: compute outside the lock to avoid blocking other threads.
        window = np.hann(size)

        with self.lock:
            # Another thread may have inserted this size while we computed.
            if size not in self.window_cache:
                # Evict the oldest non-pre-warmed entry if cache is full (fixes #2526)
                _MAX_WINDOW_CACHE = 16
                if len(self.window_cache) >= _MAX_WINDOW_CACHE:
                    _pre_warmed = {512, 1024, 2048, 4096, 8192}
                    for _evict in list(self.window_cache):
                        if _evict not in _pre_warmed:
                            del self.window_cache[_evict]
                            break
                self.window_cache[size] = window
                debug(f"Computed and cached Hanning window for size {size}")
            return self.window_cache[size]

    def parallel_windowed_fft(
        self,
        audio: np.ndarray,
        fft_size: int = 4096,
        hop_size: int | None = None,
        window: np.ndarray | None = None
    ) -> list[np.ndarray]:
        """
        Compute FFT on overlapping windows in parallel

        Args:
            audio: Input audio signal
            fft_size: FFT size
            hop_size: Hop size between windows (default: fft_size // 2)
            window: Window function (default: Hanning)

        Returns:
            List of FFT results for each window
        """
        if hop_size is None:
            hop_size = fft_size // 2

        # Get or create window
        if window is None:
            window = self.get_window(fft_size)

        # Create chunks
        chunks = []
        for i in range(0, len(audio) - fft_size + 1, hop_size):
            chunk = audio[i:i + fft_size]
            chunks.append((chunk, window, fft_size))

        # Decide on parallel vs sequential based on chunk count and config
        if not self.config.enable_parallel or len(chunks) < 2:
            # Sequential processing
            return [self._process_fft_chunk(*chunk_data) for chunk_data in chunks]

        # Determine optimal worker count
        num_workers = min(self.config.max_workers, len(chunks))

        if self.config.use_multiprocessing:
            # Use process pool for CPU-bound FFT operations
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                results = list(executor.map(self._process_fft_chunk_static, chunks))
        else:
            # Use thread pool (works well for NumPy/SciPy with GIL release)
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                results = list(executor.map(self._process_fft_chunk, *zip(*chunks)))

        return results

    def _process_fft_chunk(
        self,
        chunk: np.ndarray,
        window: np.ndarray,
        fft_size: int
    ) -> np.ndarray:
        """Process single FFT chunk"""
        # Apply window
        windowed = chunk * window

        # Compute FFT
        spectrum = np.fft.fft(windowed, fft_size)

        return spectrum

    @staticmethod
    def _process_fft_chunk_static(chunk_data: tuple[np.ndarray, np.ndarray, int]) -> np.ndarray:
        """Static method for multiprocessing"""
        chunk, window, fft_size = chunk_data
        windowed = chunk * window
        return np.fft.fft(windowed, fft_size)

    def parallel_stft(
        self,
        audio: np.ndarray,
        fft_size: int = 4096,
        hop_size: int | None = None
    ) -> np.ndarray:
        """
        Compute Short-Time Fourier Transform in parallel

        Args:
            audio: Input audio signal
            fft_size: FFT size
            hop_size: Hop size between windows

        Returns:
            STFT matrix (frequency x time)
        """
        # Compute FFTs in parallel
        fft_results = self.parallel_windowed_fft(audio, fft_size, hop_size)

        # Stack into STFT matrix
        stft_matrix = np.column_stack([fft[:fft_size // 2 + 1] for fft in fft_results])

        return stft_matrix


class ParallelBandProcessor:
    """Parallel frequency band processing"""

    def __init__(self, config: ParallelConfig | None = None) -> None:
        self.config: ParallelConfig = config or ParallelConfig()
        debug(f"Parallel band processor initialized: max_workers={self.config.max_workers}")

    def process_bands_parallel(
        self,
        audio: np.ndarray,
        band_filters: list[Callable[..., np.ndarray]],
        band_gains: np.ndarray,
        band_groups: list[list[int]] | None = None
    ) -> np.ndarray:
        """
        Process frequency bands in parallel

        Args:
            audio: Input audio signal
            band_filters: List of filter functions for each band
            band_gains: Gain values for each band
            band_groups: Optional band groupings for batch processing

        Returns:
            Processed audio signal
        """
        num_bands = len(band_filters)

        if not self.config.enable_parallel or num_bands < 2:
            # Sequential processing
            return self._process_bands_sequential(audio, band_filters, band_gains)

        # Use band grouping if enabled
        if self.config.band_grouping and band_groups:
            return self._process_band_groups(audio, band_filters, band_gains, band_groups)

        # Determine worker count
        num_workers = min(self.config.max_workers, num_bands)

        # Process bands in parallel
        if self.config.use_multiprocessing:
            # Multiprocessing for heavy filtering
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                # Prepare tasks
                tasks = [
                    (audio, band_filters[i], band_gains[i], i)
                    for i in range(num_bands)
                ]

                # Execute in parallel
                futures = [executor.submit(self._process_single_band_static, task) for task in tasks]

                # Collect results — list comprehension avoids shared-reference aliasing
                # that [np.array([])] * num_bands would create (#2424).
                band_results: list[np.ndarray] = [np.array([]) for _ in range(num_bands)]
                for future in as_completed(futures):
                    idx, result = future.result()
                    band_results[idx] = result
        else:
            # Threading for lighter operations
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Submit tasks
                futures = [
                    executor.submit(self._process_single_band, audio, band_filters[i], band_gains[i], i)
                    for i in range(num_bands)
                ]

                # Collect results — list comprehension avoids shared-reference aliasing (#2424)
                band_results = [np.array([]) for _ in range(num_bands)]
                for future in as_completed(futures):
                    idx, result = future.result()
                    band_results[idx] = result

        # Sum all band results
        output: np.ndarray = np.sum(band_results, axis=0)

        return output

    def _process_single_band(
        self,
        audio: np.ndarray,
        band_filter: Callable[..., np.ndarray],
        gain: float,
        band_idx: int
    ) -> tuple[int, np.ndarray]:
        """Process a single frequency band"""
        # Apply filter
        filtered = band_filter(audio)

        # Apply gain
        result = filtered * (10 ** (gain / 20))  # dB to linear

        return band_idx, result

    @staticmethod
    def _process_single_band_static(task_data: tuple[np.ndarray, Callable[..., np.ndarray], float, int]) -> tuple[int, np.ndarray]:
        """Static method for multiprocessing"""
        audio, band_filter, gain, band_idx = task_data
        filtered = band_filter(audio)
        result = filtered * (10 ** (gain / 20))
        return band_idx, result

    def _process_band_groups(
        self,
        audio: np.ndarray,
        band_filters: list[Callable[..., np.ndarray]],
        band_gains: np.ndarray,
        band_groups: list[list[int]]
    ) -> np.ndarray:
        """Process frequency bands in groups"""
        num_groups = len(band_groups)
        num_workers = min(self.config.max_workers, num_groups)

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit group processing tasks
            futures = [
                executor.submit(self._process_band_group, audio, band_filters, band_gains, group)
                for group in band_groups
            ]

            # Collect group results
            group_results: list[np.ndarray] = [future.result() for future in futures]

        # Sum all group results
        output: np.ndarray = np.sum(group_results, axis=0)

        return output

    def _process_band_group(
        self,
        audio: np.ndarray,
        band_filters: list[Callable[..., np.ndarray]],
        band_gains: np.ndarray,
        band_indices: list[int]
    ) -> np.ndarray:
        """Process a group of frequency bands"""
        group_result = np.zeros_like(audio)

        for band_idx in band_indices:
            filtered = band_filters[band_idx](audio)
            group_result += filtered * (10 ** (band_gains[band_idx] / 20))

        return group_result

    def _process_bands_sequential(
        self,
        audio: np.ndarray,
        band_filters: list[Callable[..., np.ndarray]],
        band_gains: np.ndarray
    ) -> np.ndarray:
        """Sequential band processing fallback"""
        result = np.zeros_like(audio)

        for band_filter, gain in zip(band_filters, band_gains):
            filtered = band_filter(audio)
            result += filtered * (10 ** (gain / 20))

        return result


class ParallelFeatureExtractor:
    """Parallel audio feature extraction"""

    def __init__(self, config: ParallelConfig | None = None) -> None:
        self.config: ParallelConfig = config or ParallelConfig()
        debug(f"Parallel feature extractor initialized")

    def extract_features_parallel(
        self,
        audio: np.ndarray,
        feature_extractors: dict[str, Callable[..., Any]]
    ) -> dict[str, Any]:
        """
        Extract multiple audio features in parallel

        Args:
            audio: Input audio signal
            feature_extractors: Dictionary of feature name -> extractor function

        Returns:
            Dictionary of feature name -> feature value
        """
        if not self.config.enable_parallel or len(feature_extractors) < 2:
            # Sequential extraction
            return {
                name: extractor(audio)
                for name, extractor in feature_extractors.items()
            }

        num_workers = min(self.config.max_workers, len(feature_extractors))

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit feature extraction tasks
            futures: dict[Any, str] = {
                executor.submit(extractor, audio): name
                for name, extractor in feature_extractors.items()
            }

            # Collect results
            features: dict[str, Any] = {}
            for future in as_completed(futures):
                feature_name = futures[future]
                features[feature_name] = future.result()

        return features


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
    ) -> list[np.ndarray]:
        """
        Process multiple audio files in parallel

        Args:
            audio_files: List of audio arrays
            process_func: Processing function to apply to each file
            max_workers: Override default max workers

        Returns:
            List of processed audio arrays
        """
        if not self.config.enable_parallel or len(audio_files) < 2:
            # Sequential processing
            return [process_func(audio) for audio in audio_files]

        num_workers = max_workers or min(self.config.max_workers, len(audio_files))

        # Use multiprocessing for batch processing (true parallelism)
        if self.config.use_multiprocessing:
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                results = list(executor.map(process_func, audio_files))
        else:
            # Threading fallback
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                results = list(executor.map(process_func, audio_files))

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


# Convenience decorator for automatic parallelization
def parallelize(max_workers: int | None = None) -> Callable[[Callable[[Any], Any]], Callable[[list[Any]], list[Any]]]:
    """Decorator to automatically parallelize a function over a list"""
    def decorator(func: Callable[[Any], Any]) -> Callable[[list[Any]], list[Any]]:
        @wraps(func)
        def wrapper(data_list: list[Any], *args: Any, **kwargs: Any) -> list[Any]:
            processor = get_parallel_processor()

            def process_item(item: Any) -> Any:
                return func(item, *args, **kwargs)

            return processor.process_batch(data_list, process_item, max_workers)

        return wrapper
    return decorator
