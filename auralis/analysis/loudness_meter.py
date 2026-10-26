"""
LUFS Loudness Measurement
~~~~~~~~~~~~~~~~~~~~~~~~~

ITU-R BS.1770-4 compliant loudness measurement implementation.
"""

from auralis.dsp.utils.conversion import AMPLITUDE_EPS, amplitude_to_db_array
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import signal

from .loudness_filters import KWeightingMixin
from .loudness_range import LoudnessRangeTracker


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


class LoudnessMeter(KWeightingMixin):
    """ITU-R BS.1770-4 compliant loudness meter"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

        # Initialize filters
        self._init_k_weighting_filter()

        # Measurement parameters
        self.block_size = int(0.4 * sample_rate)  # 400ms blocks
        self.short_term_blocks = 30  # 3 seconds worth of blocks
        self.momentary_blocks = 4   # 400ms worth of blocks

        # Storage for measurements.
        # `block_buffer` is bounded to `short_term_blocks` so the short-term
        # and momentary windows stay accurate. `integrated_buffer` is
        # unbounded and holds every block ever measured; ITU-R BS.1770
        # integrated LUFS is defined as the gated mean over the whole
        # measurement, so the integrated calculation must NOT see the
        # truncated buffer (#3466).
        self.block_buffer: list[float] = []
        self.integrated_buffer: list[float] = []
        # EBU Tech 3342 LRA needs block durations, not just levels (#5741).
        self._lra = LoudnessRangeTracker(sample_rate)

        # Peak tracking across all chunks
        self._peak: float = 0.0
        self._true_peak: float = 0.0  # 4× oversampled true peak (linear domain)

        # Total sample count for accurate measurement_duration (#3307).
        # measure_chunk callers may feed arbitrary block sizes, so we cannot
        # infer duration from len(integrated_buffer) * a hardcoded hop time.
        self._total_samples: int = 0

        # True peak measurement
        self.true_peak_buffer_size = 4
        self._init_true_peak_filter()

    def calculate_block_loudness(self, k_weighted_audio: np.ndarray) -> float:
        """Calculate loudness for a 400ms block"""
        if k_weighted_audio.ndim == 1:
            # Mono
            mean_square = np.mean(k_weighted_audio**2)
        else:
            # ITU-R BS.1770-4: sum the per-channel mean squares with a weight
            # of 1.0 per channel (correct for mono and L/R stereo). Surround
            # channels would need the 1.41 weight and LFE exclusion, which
            # needs layout metadata; callers must downmix those first (#5550).
            # Summed channel by channel, in this order, exactly as the stereo-only
            # version did: np.mean(..., axis=0) over the whole array accumulates in a
            # different order, and the last-bit difference is enough to flip blocks
            # sitting on the relative gate (test_loudness_integrated_regression).
            mean_square = sum(
                np.mean(k_weighted_audio[:, ch] ** 2) for ch in range(k_weighted_audio.shape[1])
            )

        # Convert to LUFS
        if mean_square > 0:
            lufs = float(-0.691 + 10 * np.log10(mean_square))
        else:
            lufs = -np.inf

        return float(lufs)

    def measure_chunk(self, audio_chunk: np.ndarray) -> dict[str, Any]:
        """
        Measure LUFS for an audio chunk

        Args:
            audio_chunk: Audio data (mono or stereo)

        Returns:
            Dictionary with LUFS measurements
        """
        # Accumulate real sample count for measurement_duration (#3307).
        # Works for mono (1-D) and stereo (2-D): len() returns sample-axis size.
        self._total_samples += len(audio_chunk)

        # Track sample peak and true peak across all chunks
        chunk_peak = float(np.max(np.abs(audio_chunk)))
        if chunk_peak > self._peak:
            self._peak = chunk_peak

        chunk_true_peak = self._calculate_true_peak_linear(audio_chunk)
        if chunk_true_peak > self._true_peak:
            self._true_peak = chunk_true_peak

        # Apply K-weighting
        k_weighted = self.apply_k_weighting(audio_chunk)

        # Calculate block loudness
        block_loudness = self.calculate_block_loudness(k_weighted)

        # Add to block buffer (bounded for short-term/momentary windows)
        # and integrated buffer (unbounded for ITU-R BS.1770 integrated).
        self.block_buffer.append(block_loudness)
        self.integrated_buffer.append(block_loudness)
        self._lra.add(block_loudness, len(audio_chunk))

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

    def _calculate_true_peak_linear(self, audio_chunk: np.ndarray) -> float:
        """Calculate true peak in linear domain with 4× oversampling (ITU-R BS.1770-4)"""
        if audio_chunk.ndim == 1:
            oversampled = signal.resample_poly(audio_chunk, self.oversample_factor, 1)
        else:
            oversampled = signal.resample_poly(audio_chunk, self.oversample_factor, 1, axis=0)

        return float(np.max(np.abs(oversampled)))

    def _calculate_true_peak(self, audio_chunk: np.ndarray) -> float:
        """Calculate true peak in dBFS with oversampling (ITU-R BS.1770-4 compliant)"""
        true_peak = self._calculate_true_peak_linear(audio_chunk)

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
        if not self.integrated_buffer:
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

        # Absolute gating at -70 LUFS. Read from `integrated_buffer` (not
        # the bounded `block_buffer`) so the integrated LUFS reflects the
        # entire measurement window per ITU-R BS.1770, not just the last
        # `short_term_blocks` chunks (#3466).
        gated_blocks = [b for b in self.integrated_buffer if b >= -70.0]

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

                loudness_range = self._lra.loudness_range()
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
            peak_level_dbfs=float(amplitude_to_db_array(self._peak)),
            true_peak_dbfs=float(amplitude_to_db_array(self._true_peak)),
            gating_blocks_used=len(final_gated_blocks) if 'final_gated_blocks' in locals() else 0,
            # Derive duration from actual samples fed (#3307). Prior code
            # multiplied call count by 0.1 s which assumed a 100 ms hop —
            # wrong for any caller that feeds non-100 ms chunks (e.g. the
            # fingerprint analyzer feeds 400 ms blocks).
            measurement_duration=self._total_samples / self.sample_rate
        )

    def reset(self) -> None:
        """Reset the meter for a new measurement"""
        self.block_buffer.clear()
        self.integrated_buffer.clear()
        self._lra.reset()
        self._peak = 0.0
        self._true_peak = 0.0
        self._total_samples = 0
        self.pre_filter_zi = None
        self.rlb_filter_zi = None