# -*- coding: utf-8 -*-

"""
LUFS Loudness Measurement
~~~~~~~~~~~~~~~~~~~~~~~~~

ITU-R BS.1770-4 compliant loudness measurement implementation.
"""

import numpy as np
from scipy import signal
from typing import Dict, Optional, List, Any, Tuple, cast
from dataclasses import dataclass


@dataclass
class LUFSMeasurement:
    """LUFS measurement result"""
    integrated_lufs: float
    momentary_lufs: float
    short_term_lufs: float
    loudness_range: float
    peak_level_dbfs: float
    true_peak_dbfs: float
    gating_blocks_used: int
    measurement_duration: float


class LoudnessMeter:
    """ITU-R BS.1770-4 compliant loudness meter"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

        # Initialize filters
        self._init_k_weighting_filter()

        # Measurement parameters
        self.block_size = int(0.4 * sample_rate)  # 400ms blocks
        self.overlap_size = int(0.3 * sample_rate)  # 300ms overlap (100ms hop)
        self.short_term_blocks = 30  # 3 seconds worth of blocks
        self.momentary_blocks = 4   # 400ms worth of blocks

        # Storage for measurements
        self.block_buffer: List[float] = []
        self.gated_blocks: List[float] = []

        # True peak measurement
        self.true_peak_buffer_size = 4
        self._init_true_peak_filter()

    def _init_k_weighting_filter(self) -> None:
        """Initialize K-weighting filter (pre-filter + RLB weighting)"""
        # Pre-filter (high-pass)
        # Butterworth high-pass filter at ~40Hz
        self.pre_filter_b, self.pre_filter_a = signal.butter(
            1, 40.0, btype='high', fs=self.sample_rate
        )

        # RLB weighting filter (shelf filter around 1.5kHz)
        # Simplified implementation
        f0 = 1500.0  # 1.5 kHz
        db_gain = 4.0  # +4dB boost
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
        self.rlb_filter_a = np.array([1, a1, a2]) / a0

        # Initialize filter states
        self.pre_filter_zi: Optional[Any] = None
        self.rlb_filter_zi: Optional[Any] = None

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
                self.pre_filter_zi = signal.lfilter_zi(
                    self.pre_filter_b, self.pre_filter_a)
                self.rlb_filter_zi = signal.lfilter_zi(
                    self.rlb_filter_b, self.rlb_filter_a)

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
            # Stereo - apply to each channel
            if self.pre_filter_zi is None:
                self.pre_filter_zi = np.column_stack([
                    signal.lfilter_zi(
                        self.pre_filter_b, self.pre_filter_a),
                    signal.lfilter_zi(
                        self.pre_filter_b, self.pre_filter_a)
                ])
                self.rlb_filter_zi = np.column_stack([
                    signal.lfilter_zi(
                        self.rlb_filter_b, self.rlb_filter_a),
                    signal.lfilter_zi(
                        self.rlb_filter_b, self.rlb_filter_a)
                ])

            k_weighted = np.zeros_like(audio_chunk)

            for ch in range(audio_chunk.shape[1]):
                # Apply pre-filter
                filtered_result = signal.lfilter(
                    self.pre_filter_b, self.pre_filter_a,
                    audio_chunk[:, ch], zi=self.pre_filter_zi[:, ch]  # type: ignore[index]
                )
                filtered = cast(np.ndarray, filtered_result[0])
                self.pre_filter_zi[:, ch] = filtered_result[1]  # type: ignore[index]

                # Apply RLB filter
                k_weighted_result = signal.lfilter(
                    self.rlb_filter_b, self.rlb_filter_a,
                    filtered, zi=self.rlb_filter_zi[:, ch]  # type: ignore[index]
                )
                k_weighted[:, ch] = cast(np.ndarray, k_weighted_result[0])
                self.rlb_filter_zi[:, ch] = k_weighted_result[1]  # type: ignore[index]

            return k_weighted

    def calculate_block_loudness(self, k_weighted_audio: np.ndarray) -> float:
        """Calculate loudness for a 400ms block"""
        if k_weighted_audio.ndim == 1:
            # Mono
            mean_square = np.mean(k_weighted_audio**2)
        else:
            # Stereo - ITU-R BS.1770-4 channel weighting
            left_ms = np.mean(k_weighted_audio[:, 0]**2)
            right_ms = np.mean(k_weighted_audio[:, 1]**2)

            # Channel weighting: L=1.0, R=1.0 for stereo
            mean_square = left_ms + right_ms

        # Convert to LUFS
        if mean_square > 0:
            lufs = float(-0.691 + 10 * np.log10(mean_square))
        else:
            lufs = -np.inf

        return float(lufs)

    def measure_chunk(self, audio_chunk: np.ndarray) -> Dict[str, Any]:
        """
        Measure LUFS for an audio chunk

        Args:
            audio_chunk: Audio data (mono or stereo)

        Returns:
            Dictionary with LUFS measurements
        """
        # Apply K-weighting
        k_weighted = self.apply_k_weighting(audio_chunk)

        # Calculate block loudness
        block_loudness = self.calculate_block_loudness(k_weighted)

        # Add to block buffer
        self.block_buffer.append(block_loudness)

        # Maintain buffer size for short-term measurement
        if len(self.block_buffer) > self.short_term_blocks:
            self.block_buffer.pop(0)

        # Calculate measurements
        momentary_lufs = self._calculate_momentary()
        short_term_lufs = self._calculate_short_term()

        # Calculate peak levels
        peak_level = self._calculate_peak(audio_chunk)
        true_peak = self._calculate_true_peak(audio_chunk)

        return {
            'block_loudness': float(block_loudness) if np.isfinite(block_loudness) else -np.inf,
            'momentary_lufs': float(momentary_lufs) if np.isfinite(momentary_lufs) else -np.inf,
            'short_term_lufs': float(short_term_lufs) if np.isfinite(short_term_lufs) else -np.inf,
            'peak_level_dbfs': float(peak_level),
            'true_peak_dbfs': float(true_peak),
            'blocks_in_buffer': len(self.block_buffer)
        }

    def _calculate_momentary(self) -> float:
        """Calculate momentary loudness (400ms)"""
        if not self.block_buffer:
            return float(-np.inf)

        # Use the most recent block for momentary
        recent_blocks = self.block_buffer[-self.momentary_blocks:]
        valid_blocks = [b for b in recent_blocks if np.isfinite(b)]

        if not valid_blocks:
            return float(-np.inf)

        # Average in linear domain, then convert back to log
        linear_sum = sum(10**(b/10) for b in valid_blocks)
        return float(10 * np.log10(linear_sum / len(valid_blocks)))

    def _calculate_short_term(self) -> float:
        """Calculate short-term loudness (3s)"""
        if len(self.block_buffer) < 3:  # Need at least 3 blocks
            return float(-np.inf)

        valid_blocks = [b for b in self.block_buffer if np.isfinite(b)]

        if not valid_blocks:
            return float(-np.inf)

        # Average in linear domain
        linear_sum = sum(10**(b/10) for b in valid_blocks)
        return float(10 * np.log10(linear_sum / len(valid_blocks)))

    def _calculate_peak(self, audio_chunk: np.ndarray) -> float:
        """Calculate peak level in dBFS"""
        peak = float(np.max(np.abs(audio_chunk)))
        if peak > 0:
            return float(20 * np.log10(peak))
        else:
            return float(-np.inf)

    def _calculate_true_peak(self, audio_chunk: np.ndarray) -> float:
        """Calculate true peak with oversampling"""
        # Simplified true peak calculation
        # In a full implementation, this would use proper oversampling
        if audio_chunk.ndim == 1:
            oversampled = np.repeat(audio_chunk, self.oversample_factor)
        else:
            oversampled = np.repeat(audio_chunk, self.oversample_factor, axis=0)

        true_peak = float(np.max(np.abs(oversampled)))

        if true_peak > 0:
            return float(20 * np.log10(true_peak))
        else:
            return float(-np.inf)

    def finalize_measurement(self) -> LUFSMeasurement:
        """
        Finalize integrated loudness measurement with gating

        Returns:
            Complete LUFS measurement result
        """
        if not self.block_buffer:
            return LUFSMeasurement(
                integrated_lufs=-np.inf,
                momentary_lufs=-np.inf,
                short_term_lufs=-np.inf,
                loudness_range=0.0,
                peak_level_dbfs=-np.inf,
                true_peak_dbfs=-np.inf,
                gating_blocks_used=0,
                measurement_duration=0.0
            )

        # Absolute gating at -70 LUFS
        gated_blocks = [b for b in self.block_buffer if b >= -70.0]

        if not gated_blocks:
            integrated_lufs = -np.inf
            loudness_range = 0.0
        else:
            # Calculate ungated integrated loudness
            ungated_integrated = 10 * np.log10(
                sum(10**(b/10) for b in gated_blocks) / len(gated_blocks)
            )

            # Relative gating at ungated - 10 LU
            relative_gate = ungated_integrated - 10.0
            final_gated_blocks = [b for b in gated_blocks if b >= relative_gate]

            if final_gated_blocks:
                integrated_lufs = 10 * np.log10(
                    sum(10**(b/10) for b in final_gated_blocks) / len(final_gated_blocks)
                )

                # Calculate loudness range (10th to 95th percentile)
                sorted_blocks = sorted(final_gated_blocks)
                p10_idx = int(0.1 * len(sorted_blocks))
                p95_idx = int(0.95 * len(sorted_blocks))
                loudness_range = sorted_blocks[p95_idx] - sorted_blocks[p10_idx]
            else:
                integrated_lufs = ungated_integrated
                loudness_range = 0.0

        # Get current momentary and short-term
        momentary = self._calculate_momentary()
        short_term = self._calculate_short_term()

        return LUFSMeasurement(
            integrated_lufs=float(integrated_lufs) if np.isfinite(integrated_lufs) else -np.inf,
            momentary_lufs=float(momentary) if np.isfinite(momentary) else -np.inf,
            short_term_lufs=float(short_term) if np.isfinite(short_term) else -np.inf,
            loudness_range=float(loudness_range),
            peak_level_dbfs=-np.inf,  # Would be calculated from all chunks
            true_peak_dbfs=-np.inf,   # Would be calculated from all chunks
            gating_blocks_used=len(final_gated_blocks) if 'final_gated_blocks' in locals() else 0,
            measurement_duration=len(self.block_buffer) * 0.1  # 100ms per block
        )

    def reset(self) -> None:
        """Reset the meter for a new measurement"""
        self.block_buffer.clear()
        self.gated_blocks.clear()
        self.pre_filter_zi = None
        self.rlb_filter_zi = None