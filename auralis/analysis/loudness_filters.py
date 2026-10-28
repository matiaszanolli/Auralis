"""
BS.1770 K-weighting filter chain for LoudnessMeter (split from
loudness_meter.py, #5838): the two-stage pre-filter / RLB design, its
streaming application, and the true-peak oversampling filter.
"""

from typing import Any, cast

import numpy as np
from scipy import signal


# BS.1770-4 Annex 1 filter parameters, the values the 48 kHz tables in the standard were
# derived from (also what pyloudnorm and ffmpeg's ebur128 use).
_SHELF_GAIN_DB = 3.999843853973347
_SHELF_Q = 0.7071752369554196
_SHELF_FC_HZ = 1681.9744509555319
_RLB_Q = 0.5003270373253953
_RLB_FC_HZ = 38.13547087613982


def _head_shelf(fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Stage-1 high-shelf biquad (+4 dB above ~1.7 kHz), normalised to a0 = 1."""
    k = np.tan(np.pi * _SHELF_FC_HZ / fs)
    vh = 10 ** (_SHELF_GAIN_DB / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / _SHELF_Q + k * k
    b = np.array([vh + vb * k / _SHELF_Q + k * k, 2 * (k * k - vh), vh - vb * k / _SHELF_Q + k * k]) / a0
    a = np.array([1.0, 2 * (k * k - 1) / a0, (1 - k / _SHELF_Q + k * k) / a0])
    return b, a


def _rlb_highpass(fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Stage-2 RLB high-pass: a double zero at DC and Q ~ 0.5003 (not a Butterworth 0.707)."""
    k = np.tan(np.pi * _RLB_FC_HZ / fs)
    a0 = 1 + k / _RLB_Q + k * k
    return np.array([1.0, -2.0, 1.0]), np.array([1.0, 2 * (k * k - 1) / a0, (1 - k / _RLB_Q + k * k) / a0])


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
        self.pre_filter_b, self.pre_filter_a = _rlb_highpass(self.sample_rate)
        self.rlb_filter_b, self.rlb_filter_a = _head_shelf(self.sample_rate)

        # Initialize filter states
        self.pre_filter_zi: Any | None = None
        self.rlb_filter_zi: Any | None = None

    def _init_true_peak_filter(self) -> None:
        """Initialize 4x oversampling filter for true peak measurement"""
        # Simple 4x oversampling with linear interpolation
        # In a full implementation, this would use a proper anti-aliasing filter
        self.oversample_factor = 4

    def apply_k_weighting(self, audio_chunk: np.ndarray) -> np.ndarray:
        """Apply K-weighting filter to audio"""
        if audio_chunk.ndim == 1:
            # Mono
            if self.pre_filter_zi is None:
                # Scale initial conditions by first sample to minimize transients
                self.pre_filter_zi = (
                    signal.lfilter_zi(self.pre_filter_b, self.pre_filter_a)
                    * audio_chunk[0]
                )
                self.rlb_filter_zi = (
                    signal.lfilter_zi(self.rlb_filter_b, self.rlb_filter_a)
                    * audio_chunk[0]
                )

            # Apply pre-filter
            filtered_tuple = signal.lfilter(
                self.pre_filter_b, self.pre_filter_a, audio_chunk, zi=self.pre_filter_zi
            )
            filtered: np.ndarray = cast(np.ndarray, filtered_tuple[0])
            self.pre_filter_zi = filtered_tuple[1]

            # Apply RLB filter
            k_weighted_tuple = signal.lfilter(
                self.rlb_filter_b, self.rlb_filter_a, filtered, zi=self.rlb_filter_zi
            )
            k_weighted: np.ndarray = cast(np.ndarray, k_weighted_tuple[0])
            self.rlb_filter_zi = k_weighted_tuple[1]

            return k_weighted

        else:
            # Multichannel (including a single-column (N, 1) array) - one
            # filter state column per channel, sized from the actual channel
            # count rather than assumed to be two (#5550).
            if self.pre_filter_zi is None:
                pre_zi = signal.lfilter_zi(self.pre_filter_b, self.pre_filter_a)
                rlb_zi = signal.lfilter_zi(self.rlb_filter_b, self.rlb_filter_a)
                # Scale initial conditions by first sample per channel
                self.pre_filter_zi = np.column_stack(
                    [pre_zi * audio_chunk[0, ch] for ch in range(audio_chunk.shape[1])]
                )
                self.rlb_filter_zi = np.column_stack(
                    [rlb_zi * audio_chunk[0, ch] for ch in range(audio_chunk.shape[1])]
                )

            k_weighted = np.zeros_like(audio_chunk)

            for ch in range(audio_chunk.shape[1]):
                # Apply pre-filter
                filtered_result = signal.lfilter(
                    self.pre_filter_b, self.pre_filter_a,
                    audio_chunk[:, ch], zi=self.pre_filter_zi[:, ch]
                )
                filtered = cast(np.ndarray, filtered_result[0])
                self.pre_filter_zi[:, ch] = filtered_result[1]

                # Apply RLB filter
                k_weighted_result = signal.lfilter(
                    self.rlb_filter_b, self.rlb_filter_a,
                    filtered, zi=self.rlb_filter_zi[:, ch]
                )
                k_weighted[:, ch] = cast(np.ndarray, k_weighted_result[0])
                self.rlb_filter_zi[:, ch] = k_weighted_result[1]

            return k_weighted
