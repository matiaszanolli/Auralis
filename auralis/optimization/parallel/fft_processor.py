"""
Parallel FFT Processor
~~~~~~~~~~~~~~~~~~~~~~~

Parallel FFT / STFT computation for spectrum analysis (#4276).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any

import numpy as np
from scipy.signal.windows import hann

from ...utils.logging import debug
from .config import ParallelConfig


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
            self.window_cache[size] = hann(size)
            debug(f"Cached Hanning window for size {size}")

    def get_window(self, size: int) -> np.ndarray:
        """Get window function (cached or compute).

        Uses a double-check pattern so that hann() — which can be
        expensive for large sizes — is computed outside the lock, preventing
        all parallel threads from serialising on the first cache miss (#2077).

        #3791: the fast-path read uses `dict.get(...)` instead of an
        `in`-then-`[]` pair. The previous form raced with the slow path's
        cache-full eviction at lines 77-82 — a concurrent thread could
        evict the slot between the `in` check and the bracket access,
        raising `KeyError`. `dict.get(...)` is atomic in CPython, so the
        fast path never sees a half-deleted entry.
        """
        # Fast path: common sizes are pre-warmed in __init__, no lock needed.
        cached = self.window_cache.get(size)
        if cached is not None:
            return cached

        # Slow path: compute outside the lock to avoid blocking other threads.
        window = hann(size)

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

        # Guard: zero-pad sub-FFT-size audio to produce a single valid frame
        # instead of silently returning empty (fixes #3439).
        if len(audio) < fft_size:
            padded = np.zeros(fft_size, dtype=audio.dtype)
            padded[:len(audio)] = audio
            return [self._process_fft_chunk(padded, window, fft_size)]

        # #3761: mark the shared window read-only so a future
        # `_process_fft_chunk` regression that mutates it raises
        # immediately instead of silently corrupting all other
        # workers. The chunk per call is already per-worker copied
        # via `audio[i:i+fft_size].copy()` below.
        window = window.view()
        window.setflags(write=False)

        # Create chunks
        chunks = []
        for i in range(0, len(audio) - fft_size + 1, hop_size):
            chunk = audio[i:i + fft_size].copy()
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
