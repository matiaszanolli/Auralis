"""
BS.1770 K-weighting filter chain for LoudnessMeter (split from
loudness_meter.py, #5838): the two-stage pre-filter / RLB design, its
streaming application, and the true-peak oversampling filter.
"""

from collections.abc import Iterator
from typing import Any, cast

import numpy as np
from scipy import signal

from .loudness_filter_design import head_shelf, rlb_highpass


class KWeightingMixin:
    """Filter state lives on the meter; ``__init__`` there calls the ``_init_*`` methods."""

    sample_rate: int
    oversample_factor: int
    true_peak_buffer_size: int
    _total_samples: int
    pre_filter_b: Any
    pre_filter_a: Any
    pre_filter_zi: Any
    rlb_filter_b: Any
    rlb_filter_a: Any
    rlb_filter_zi: Any

    def _init_k_weighting_filter(self) -> None:
        """Initialize the BS.1770-4 K-weighting chain at ``self.sample_rate``.

        ``pre_filter_*`` is the 2nd-order RLB high-pass and ``rlb_filter_*`` the
        high-shelf (the names predate the standard's stage numbering; the chain
        is linear, so the order does not matter). Both are derived from the
        analog prototypes with the bilinear transform (#5593), which reproduces
        the standard's 48 kHz coefficients exactly and extends them to any rate.
        """
        self.pre_filter_b, self.pre_filter_a = rlb_highpass(self.sample_rate)
        self.rlb_filter_b, self.rlb_filter_a = head_shelf(self.sample_rate)

        # Initialize filter states
        self.pre_filter_zi: Any | None = None
        self.rlb_filter_zi: Any | None = None

    def _init_true_peak_filter(self) -> None:
        """Initialize 4x oversampling filter for true peak measurement"""
        # Simple 4x oversampling with linear interpolation
        # In a full implementation, this would use a proper anti-aliasing filter
        self.oversample_factor = 4

    def _k_weighted_channels(self, audio_chunk: np.ndarray) -> Iterator[np.ndarray]:
        """K-weight each column of a 2-D chunk in turn (float64), carrying the filter state.

        One state column per channel, sized from the actual channel count (#5550)
        and seeded from each channel's first sample to minimise the start-up
        transient. Yielding a channel at a time lets a caller that only needs
        per-channel statistics never hold the whole filtered array (#6717).
        """
        if self.pre_filter_zi is None:
            pre_zi = signal.lfilter_zi(self.pre_filter_b, self.pre_filter_a)
            rlb_zi = signal.lfilter_zi(self.rlb_filter_b, self.rlb_filter_a)
            self.pre_filter_zi = np.column_stack([pre_zi * v for v in audio_chunk[0]])
            self.rlb_filter_zi = np.column_stack([rlb_zi * v for v in audio_chunk[0]])
        for ch in range(audio_chunk.shape[1]):
            filtered, self.pre_filter_zi[:, ch] = signal.lfilter(
                self.pre_filter_b, self.pre_filter_a, audio_chunk[:, ch], zi=self.pre_filter_zi[:, ch]
            )
            k_weighted, self.rlb_filter_zi[:, ch] = signal.lfilter(
                self.rlb_filter_b, self.rlb_filter_a, filtered, zi=self.rlb_filter_zi[:, ch]
            )
            del filtered
            yield cast(np.ndarray, k_weighted)
            del k_weighted

    def apply_k_weighting(self, audio_chunk: np.ndarray) -> np.ndarray:
        """Apply K-weighting: float64 for a 1-D chunk, the input dtype per column for 2-D."""
        if audio_chunk.ndim == 1:
            return next(self._k_weighted_channels(audio_chunk.reshape(-1, 1)))
        k_weighted = np.zeros_like(audio_chunk)
        for ch, column in enumerate(self._k_weighted_channels(audio_chunk)):
            k_weighted[:, ch] = column
        return k_weighted

    def k_weighted_mean_square(self, audio_chunk: np.ndarray) -> Any:
        """``calculate_block_loudness``'s mean square of a 2-D chunk, without the filtered array.

        Same values, order and dtype as squaring the columns of
        ``apply_k_weighting(audio_chunk)``, a column at a time (#6717).
        """
        return sum(
            np.mean(column.astype(audio_chunk.dtype, copy=False) ** 2)
            for column in self._k_weighted_channels(audio_chunk)
        )


def mean_square_to_lufs(mean_square: Any) -> float:
    """BS.1770 block loudness from a summed mean square; -inf for silence."""
    return float(-0.691 + 10 * np.log10(mean_square)) if mean_square > 0 else float(-np.inf)
