"""
Parallel Band Processor
~~~~~~~~~~~~~~~~~~~~~~~~

Parallel frequency-band filtering with per-band / per-group fallbacks (#4276).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from collections.abc import Callable

import numpy as np

from ...utils.logging import debug, warning
from .config import ParallelConfig


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

        # Process bands in parallel.
        # Each worker receives its own copy of the input audio so that an
        # in-place mutation by one band filter cannot corrupt sibling
        # workers' inputs (fixes #3355 / CONC-11). The process-pool path
        # copies via pickling, but we copy explicitly there too for symmetry.
        use_mp = self.config.use_multiprocessing
        if use_mp:
            # #3699: ProcessPoolExecutor pickles the band_filter callable.
            # Lambdas, closures, and bound methods raise PicklingError; the
            # per-future `except Exception` would silently downgrade *every*
            # band to the gainless fallback. Validate up front and downgrade
            # to threading with a single warning instead.
            import pickle
            try:
                for f in band_filters:
                    pickle.dumps(f)
            except (pickle.PicklingError, AttributeError, TypeError) as exc:
                warning(
                    f"use_multiprocessing=True requested but band_filter is not "
                    f"picklable ({exc!r}); falling back to threading. Use "
                    f"module-level functions (no lambdas/closures) if you need "
                    f"true multiprocessing."
                )
                use_mp = False
        if use_mp:
            # Multiprocessing for heavy filtering
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                # Prepare tasks
                tasks = [
                    (audio.copy(), band_filters[i], band_gains[i], i)
                    for i in range(num_bands)
                ]

                # Execute in parallel
                future_to_band = {
                    executor.submit(self._process_single_band_static, task): i
                    for i, task in enumerate(tasks)
                }

                # Pre-compute unprocessed band signals as fallback for failed bands
                # (return filtered + gain-corrected signal instead of silence —
                # fixes #3430 and #3675: previously omitted the gain multiply
                # so an EQ cut became a pass-through and a boost became neutral).
                band_fallbacks: list[np.ndarray] = [
                    band_filters[i](audio) * (10 ** (band_gains[i] / 20))
                    for i in range(num_bands)
                ]
                band_results: list[np.ndarray] = list(band_fallbacks)
                for future in as_completed(future_to_band):
                    band_i = future_to_band[future]
                    try:
                        idx, result = future.result()
                        band_results[idx] = result
                    except Exception as exc:
                        warning(f"Band {band_i} processing failed (process pool), using unprocessed signal: {exc}")
        else:
            # Threading for lighter operations
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Pre-compute unprocessed band signals as fallback (#3430) BEFORE
                # submitting workers so the main thread's reads of `audio` don't
                # race with concurrent workers (#3355).
                # #3675: include the gain multiply so a failed band contributes
                # at its configured level (not 0 dB).
                band_fallbacks = [
                    band_filters[i](audio) * (10 ** (band_gains[i] / 20))
                    for i in range(num_bands)
                ]

                # Submit tasks — each worker gets its own copy of `audio`
                # so an in-place band filter cannot corrupt siblings (#3355).
                futures_with_idx = [
                    (i, executor.submit(self._process_single_band, audio.copy(), band_filters[i], band_gains[i], i))
                    for i in range(num_bands)
                ]

                band_results = list(band_fallbacks)
                for band_i, future in futures_with_idx:
                    try:
                        idx, result = future.result()
                        band_results[idx] = result
                    except Exception as exc:
                        warning(f"Band {band_i} processing failed (thread pool), using unprocessed signal: {exc}")

        # #3760: sum all band results, preserving the input dtype.
        # `np.sum` promotes to the highest dtype seen across the worker
        # results, so a single float64 entry (e.g. from scipy's
        # `sosfiltfilt`) promotes the entire output to float64 — same
        # dtype-drift class as #3658 / #3659 / #2450 / #3752. Cast back
        # explicitly.
        output: np.ndarray = np.sum(band_results, axis=0).astype(audio.dtype, copy=False)

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
            # Each group worker receives its own copy of `audio` so an
            # in-place band filter cannot corrupt sibling groups (#3355).
            futures = [
                executor.submit(self._process_band_group, audio.copy(), band_filters, band_gains, group)
                for group in band_groups
            ]

            # Collect group results — failed groups fall back to unprocessed
            # band sum for that group rather than silence (fixes #3430).
            group_results: list[np.ndarray] = [np.zeros_like(audio) for _ in range(num_groups)]
            for i, future in enumerate(futures):
                try:
                    group_results[i] = future.result()
                except Exception as exc:
                    warning(f"Band group {i} processing failed, using unprocessed signal: {exc}")
                    # Fall back to gain-corrected sum of this group's bands.
                    # #3675: include the gain multiply so the failed group's
                    # contribution matches its configured per-band levels.
                    for band_idx in band_groups[i]:
                        # Pass a copy like the worker path (#4229): an in-place
                        # band filter would otherwise corrupt `audio` for the
                        # remaining fallback iterations.
                        group_results[i] += (
                            band_filters[band_idx](audio.copy())
                            * (10 ** (band_gains[band_idx] / 20))
                        )

        # Sum all group results. Cast back to the input dtype (#4125): np.sum
        # promotes to the widest worker dtype, so a single float64 result (e.g.
        # from scipy sosfiltfilt) would promote float32 input to float64 —
        # matching the sibling band-summation path's #3760 fix.
        output: np.ndarray = np.sum(group_results, axis=0).astype(audio.dtype, copy=False)

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
