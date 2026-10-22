"""
BS.1770 K-weighting filter chain for LoudnessMeter (split from
loudness_meter.py, #5838): the two-stage pre-filter / RLB design, its
streaming application, and the true-peak oversampling filter.
"""

from typing import Any, cast

import numpy as np
from scipy import signal


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
        """Initialize K-weighting filter (ITU-R BS.1770-4 pre-filter + RLB)"""
        # Stage 1: 2nd-order Butterworth high-pass at 38.135 Hz (BS.1770-4 Annex 1)
        # Previously: 1st-order at 40 Hz (wrong order and wrong corner frequency)
        self.pre_filter_b, self.pre_filter_a = signal.butter(
            2, 38.13475657, btype='high', fs=self.sample_rate
        )

        # Stage 2: High-shelf at 1681.974 Hz +3.999843 dB (BS.1770-4 Annex 1)
        # Previously: 1500 Hz +4 dB (shelf freq off by ~1.8 semitones)
        f0 = 1681.974450955533   # ITU-R BS.1770-4 pre-filter shelf frequency
        db_gain = 3.999843853973347  # BS.1770-4 shelf gain
        q = 1 / np.sqrt(2)

        w0 = 2 * np.pi * f0 / self.sample_rate
        cos_w0 = np.cos(w0)
        sin_w0 = np.sin(w0)
        A = 10**(db_gain / 40)
        alpha = sin_w0 / (2 * q)

        # High shelf filter coefficients
        b0 = A * ((A + 1) + (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
        b2 = A * ((A + 1) + (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha)
        a0 = (A + 1) - (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha
        a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
        a2 = (A + 1) - (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha

        self.rlb_filter_b = np.array([b0, b1, b2]) / a0
        self.rlb_filter_a = np.array([a0, a1, a2]) / a0

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
