"""
Dynamics-oriented metrics for DynamicRangeAnalyzer (split from
dynamic_range.py, #5838): compression ratio, attack time, envelope shape and
the loudness-war assessment.
"""

from typing import Any

import numpy as np
from scipy import signal

from auralis.analysis.fingerprint.metrics import (
    AggregationUtils,
    AudioMetrics,
    MetricUtils,
)

_HILBERT_MAX_SECONDS = 30


class DynamicsMetricsMixin:
    """Methods that read ``sample_rate`` set by DynamicRangeAnalyzer.__init__."""

    sample_rate: int

    def _get_dynamic_range_recommendations(self, crest_factor: float, dr_value: float) -> list[str]:
        raise NotImplementedError

    def _estimate_compression_ratio(self, audio: np.ndarray) -> float:
        """Estimate compression ratio from audio analysis"""
        # This is a simplified estimation method
        # Real compression detection would require more sophisticated analysis

        # Calculate envelope (cap to avoid multi-GB allocation on long tracks)
        _cap = int(self.sample_rate * _HILBERT_MAX_SECONDS)
        envelope = np.abs(signal.hilbert(audio[:_cap]))

        # Smooth envelope
        envelope_smooth = signal.filtfilt([1/100]*100, [1], envelope)

        # Look for compression characteristics
        # Compressed audio tends to have less dynamic variation in the envelope

        if len(envelope_smooth) < 1000:
            return 1.0

        # Calculate ratio of envelope variation to input variation
        input_variation = np.var(np.abs(audio))
        envelope_variation = np.var(envelope_smooth)

        if input_variation > 0:
            variation_ratio = envelope_variation / input_variation
            # Convert to compression ratio estimate (very rough)
            compression_ratio = 1.0 / max(0.1, variation_ratio)
        else:
            compression_ratio = 1.0

        # Normalize compression ratio to 1-20 range using MetricUtils
        # Normalize to 0-1 first (1.0 → 0, 20.0 → 1)
        normalized = MetricUtils.normalize_to_range(compression_ratio - 1.0, 19.0, clip=True)
        # Scale back to 1-20 range
        return 1.0 + normalized * 19.0

    def _estimate_attack_time(self, audio: np.ndarray) -> float:
        """Estimate compressor attack time from transient analysis"""
        # Find sudden level increases (transients)
        # Flatten audio in case it's 2D; cap to avoid multi-GB allocation on long tracks
        audio_flat = audio.flatten()
        _cap = int(self.sample_rate * _HILBERT_MAX_SECONDS)
        envelope = np.abs(signal.hilbert(audio_flat[:_cap]))

        # Calculate derivative to find rapid changes
        envelope_diff = np.diff(envelope)

        # Check if we have enough data
        if len(envelope_diff) == 0:
            return 0.01  # Default 10ms for too short signals

        # Find positive transients
        transient_threshold = np.percentile(envelope_diff, 95)
        transients = np.where(envelope_diff > transient_threshold)[0]

        if len(transients) == 0:
            return 0.01  # Default 10ms

        # Analyze how quickly the level is attenuated after transients
        attack_times = []

        for transient_idx in transients[:10]:  # Analyze first 10 transients
            if transient_idx + 1000 < len(envelope):  # Need at least 1000 samples after
                # Look at envelope after transient
                post_transient = envelope[transient_idx:transient_idx + 1000]

                # Find where it settles (reaches 90% of final value)
                final_value = post_transient[-100:].mean()  # Average of last 100 samples
                target_value = 0.9 * final_value

                # Find settling time
                settle_idx = np.where(post_transient <= target_value)[0]
                if len(settle_idx) > 0:
                    attack_samples = settle_idx[0]
                    attack_time = attack_samples / self.sample_rate
                    attack_times.append(attack_time)

        if attack_times:
            # Aggregate attack times using median for robustness to outliers
            attack_times_array = np.array(attack_times)
            return AggregationUtils.aggregate_frames_to_track(attack_times_array, method='median')
        else:
            return 0.01  # Default 10ms

    def _analyze_envelope(self, audio: np.ndarray) -> dict[str, Any]:
        """Analyze audio envelope characteristics"""
        # Calculate envelope using Hilbert transform
        # Flatten audio and cap to avoid multi-GB allocation on long tracks
        audio_flat = audio.flatten()
        _cap = int(self.sample_rate * _HILBERT_MAX_SECONDS)
        envelope = np.abs(signal.hilbert(audio_flat[:_cap]))

        # Smooth the envelope
        window_size = int(0.01 * self.sample_rate)  # 10ms smoothing
        if window_size > 0 and len(envelope) > window_size * 3:  # filtfilt needs 3x window size
            envelope_smooth = signal.filtfilt(
                np.ones(window_size)/window_size, [1], envelope
            )
        else:
            envelope_smooth = envelope

        # Calculate envelope statistics using safe log conversion
        envelope_db = AudioMetrics.rms_to_db(envelope_smooth)

        # Attack and release characteristics
        envelope_diff = np.diff(envelope_smooth)
        attack_rate = np.mean(envelope_diff[envelope_diff > 0]) if np.any(envelope_diff > 0) else 0
        release_rate = np.mean(np.abs(envelope_diff[envelope_diff < 0])) if np.any(envelope_diff < 0) else 0

        return {
            'envelope_range_db': float(np.ptp(envelope_db[np.isfinite(envelope_db)])),
            'envelope_variance': float(np.var(envelope_db[np.isfinite(envelope_db)])),
            'average_attack_rate': float(attack_rate),
            'average_release_rate': float(release_rate),
            'envelope_smoothness': float(1.0 / (1.0 + np.var(envelope_diff))),
            'envelope_percentiles': {
                'p10': float(np.percentile(envelope_db[np.isfinite(envelope_db)], 10)),
                'p50': float(np.percentile(envelope_db[np.isfinite(envelope_db)], 50)),
                'p90': float(np.percentile(envelope_db[np.isfinite(envelope_db)], 90))
            }
        }

    def _assess_loudness_war(self, crest_factor: float, dr_value: float) -> dict[str, Any]:
        """Assess if audio shows signs of loudness war processing"""
        # Indicators of loudness war:
        # - Very low crest factor (< 6dB)
        # - Very low DR value (< 7)
        # - Excessive limiting/compression

        loudness_war_score = 0

        if crest_factor < 6:
            loudness_war_score += 2
        elif crest_factor < 10:
            loudness_war_score += 1

        if dr_value < 7:
            loudness_war_score += 2
        elif dr_value < 10:
            loudness_war_score += 1

        # Assess severity
        if loudness_war_score >= 3:
            severity = "High"
            description = "Heavily processed with excessive limiting"
        elif loudness_war_score >= 2:
            severity = "Medium"
            description = "Moderately compressed/limited"
        elif loudness_war_score >= 1:
            severity = "Low"
            description = "Some compression/limiting applied"
        else:
            severity = "None"
            description = "Natural dynamic range preserved"

        return {
            'loudness_war_score': int(loudness_war_score),
            'severity': severity,
            'description': description,
            'recommendations': self._get_dynamic_range_recommendations(crest_factor, dr_value)
        }
