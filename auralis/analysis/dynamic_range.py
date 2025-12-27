# -*- coding: utf-8 -*-

"""
Dynamic Range Analysis
~~~~~~~~~~~~~~~~~~~~~

Comprehensive dynamic range measurement and analysis tools.
"""

from typing import Any, Dict, List, Tuple

import numpy as np
from scipy import signal

from auralis.analysis.fingerprint.common_metrics import (
    AggregationUtils,
    AudioMetrics,
    MetricUtils,
)


class DynamicRangeAnalyzer:
    """Comprehensive dynamic range analysis"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

        # Analysis parameters
        self.rms_window_size = int(0.05 * sample_rate)  # 50ms RMS window
        self.peak_hold_time = int(0.5 * sample_rate)    # 500ms peak hold
        self.gate_threshold = -70.0  # dBFS gating threshold

        # Crest factor analysis
        self.crest_history: List[float] = []
        self.max_crest_history = 200  # Keep 10 seconds at 20Hz

    def analyze_dynamic_range(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """
        Comprehensive dynamic range analysis

        Args:
            audio_data: Audio data (mono or stereo)

        Returns:
            Dictionary with dynamic range metrics
        """
        if audio_data.ndim == 2:
            # For stereo, analyze sum of channels
            audio_mono = np.sum(audio_data, axis=1) / 2
        else:
            audio_mono = audio_data

        # Basic level measurements
        peak_level = self._calculate_peak_level(audio_mono)
        rms_level = self._calculate_rms_level(audio_mono)
        crest_factor = peak_level - rms_level

        # Dynamic range measurements
        dr_value = self._calculate_dr_value(audio_mono)
        plr = self._calculate_plr(audio_mono)

        # Temporal analysis
        rms_variation = self._analyze_rms_variation(audio_mono)
        peak_distribution = self._analyze_peak_distribution(audio_mono)

        # Compression detection
        compression_ratio = self._estimate_compression_ratio(audio_mono)
        attack_time = self._estimate_attack_time(audio_mono)

        # Envelope analysis
        envelope_stats = self._analyze_envelope(audio_mono)

        # Update crest factor history
        self.crest_history.append(crest_factor)
        if len(self.crest_history) > self.max_crest_history:
            self.crest_history.pop(0)

        return {
            'peak_level_dbfs': float(peak_level),
            'rms_level_dbfs': float(rms_level),
            'crest_factor_db': float(crest_factor),
            'dr_value': float(dr_value),
            'peak_to_loudness_ratio': float(plr),
            'rms_variation': rms_variation,
            'peak_distribution': peak_distribution,
            'compression_ratio': float(compression_ratio),
            'estimated_attack_time_ms': float(attack_time * 1000),
            'envelope_stats': envelope_stats,
            'dynamic_range_category': self._categorize_dynamic_range(dr_value),
            'loudness_war_indicator': self._assess_loudness_war(crest_factor, dr_value)
        }

    def _calculate_peak_level(self, audio: np.ndarray) -> float:
        """Calculate peak level in dBFS"""
        peak = np.max(np.abs(audio))
        if peak > 0:
            return 20 * np.log10(peak)  # type: ignore[no-any-return]
        else:
            return -np.inf

    def _calculate_rms_level(self, audio: np.ndarray) -> float:
        """Calculate RMS level in dBFS"""
        rms = np.sqrt(np.mean(audio**2))
        if rms > 0:
            return 20 * np.log10(rms)  # type: ignore[no-any-return]
        else:
            return -np.inf

    def _calculate_dr_value(self, audio: np.ndarray) -> float:
        """
        Calculate Dynamic Range (DR) value using EBU method
        This is a simplified implementation
        """
        # Divide into 3-second blocks
        block_duration = 3.0  # seconds
        block_samples = int(block_duration * self.sample_rate)

        if len(audio) < block_samples:
            return 0.0

        # Calculate peak and RMS for each block
        peak_values = []
        rms_values = []

        for i in range(0, len(audio) - block_samples, block_samples):
            block = audio[i:i + block_samples]

            peak_db = self._calculate_peak_level(block)
            rms_db = self._calculate_rms_level(block)

            if np.isfinite(peak_db) and np.isfinite(rms_db):
                peak_values.append(peak_db)
                rms_values.append(rms_db)

        if not peak_values or not rms_values:
            return 0.0

        # Calculate DR as difference between 95th percentile peak and average RMS
        peak_95th = np.percentile(peak_values, 95)
        rms_average = np.mean(rms_values)

        dr_value = peak_95th - rms_average

        return max(0.0, dr_value)  # type: ignore[return-value]  # DR cannot be negative

    def _calculate_plr(self, audio: np.ndarray) -> float:
        """Calculate Peak-to-Loudness Ratio"""
        peak_level = self._calculate_peak_level(audio)

        # Simple loudness estimate (not true LUFS, but correlated)
        # Use A-weighted RMS as loudness approximation
        loudness_estimate = self._calculate_rms_level(audio)

        if np.isfinite(peak_level) and np.isfinite(loudness_estimate):
            return peak_level - loudness_estimate
        else:
            return 0.0

    def _analyze_rms_variation(self, audio: np.ndarray) -> Dict[str, Any]:
        """Analyze RMS variation over time"""
        # Calculate RMS in sliding windows
        hop_size = self.rms_window_size // 2
        rms_values = []

        for i in range(0, len(audio) - self.rms_window_size, hop_size):
            window = audio[i:i + self.rms_window_size]
            rms = np.sqrt(np.mean(window**2))
            if rms > 0:
                rms_db = 20 * np.log10(rms)
                rms_values.append(rms_db)

        if not rms_values:
            return {
                'rms_range_db': 0.0,
                'rms_variance': 0.0,
                'rms_stability': 1.0
            }

        rms_values = np.array(rms_values)  # type: ignore[assignment]
        finite_rms = rms_values[np.isfinite(rms_values)]

        if len(finite_rms) == 0:
            return {
                'rms_range_db': 0.0,
                'rms_variance': 0.0,
                'rms_stability': 1.0
            }

        rms_range = np.ptp(finite_rms)  # Peak-to-peak range
        rms_variance = np.var(finite_rms)
        rms_stability = 1.0 / (1.0 + rms_variance)  # Higher variance = lower stability

        return {
            'rms_range_db': float(rms_range),
            'rms_variance': float(rms_variance),
            'rms_stability': float(rms_stability),
            'rms_percentiles': {
                'p5': float(np.percentile(finite_rms, 5)),
                'p50': float(np.percentile(finite_rms, 50)),
                'p95': float(np.percentile(finite_rms, 95))
            }
        }

    def _analyze_peak_distribution(self, audio: np.ndarray) -> Dict[str, Any]:
        """Analyze distribution of peak levels"""
        # Find peaks using scipy
        peaks, properties = signal.find_peaks(np.abs(audio), height=0.01, distance=100)

        if len(peaks) == 0:
            return {
                'peak_count': 0,
                'peak_density': 0.0,
                'average_peak_level_db': -np.inf,
                'peak_level_variance': 0.0
            }

        peak_amplitudes = np.abs(audio[peaks])
        # Use SafeOperations for safe log conversion with epsilon protection
        peak_levels_db = AudioMetrics.rms_to_db(peak_amplitudes)

        # Calculate peak density (peaks per second)
        duration_seconds = len(audio) / self.sample_rate
        peak_density = len(peaks) / duration_seconds

        return {
            'peak_count': int(len(peaks)),
            'peak_density': float(peak_density),
            'average_peak_level_db': float(np.mean(peak_levels_db)),
            'peak_level_variance': float(np.var(peak_levels_db)),
            'max_peak_level_db': float(np.max(peak_levels_db)),
            'peak_distribution': {
                'p25': float(np.percentile(peak_levels_db, 25)),
                'p50': float(np.percentile(peak_levels_db, 50)),
                'p75': float(np.percentile(peak_levels_db, 75)),
                'p95': float(np.percentile(peak_levels_db, 95))
            }
        }

    def _estimate_compression_ratio(self, audio: np.ndarray) -> float:
        """Estimate compression ratio from audio analysis"""
        # This is a simplified estimation method
        # Real compression detection would require more sophisticated analysis

        # Calculate envelope
        envelope = np.abs(signal.hilbert(audio))

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
        # Flatten audio in case it's 2D
        audio_flat = audio.flatten()
        envelope = np.abs(signal.hilbert(audio_flat))

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

    def _analyze_envelope(self, audio: np.ndarray) -> Dict[str, Any]:
        """Analyze audio envelope characteristics"""
        # Calculate envelope using Hilbert transform
        # Flatten audio in case it's 2D
        audio_flat = audio.flatten()
        envelope = np.abs(signal.hilbert(audio_flat))

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

    def _categorize_dynamic_range(self, dr_value: float) -> str:
        """Categorize dynamic range value"""
        if dr_value >= 20:
            return "Excellent"
        elif dr_value >= 14:
            return "Very Good"
        elif dr_value >= 10:
            return "Good"
        elif dr_value >= 7:
            return "Fair"
        elif dr_value >= 4:
            return "Poor"
        else:
            return "Very Poor"

    def _assess_loudness_war(self, crest_factor: float, dr_value: float) -> Dict[str, Any]:
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

    def _get_dynamic_range_recommendations(self, crest_factor: float, dr_value: float) -> List[str]:
        """Get recommendations for improving dynamic range"""
        recommendations = []

        if crest_factor < 6:
            recommendations.append("Consider reducing limiter/compressor intensity")

        if dr_value < 7:
            recommendations.append("Increase dynamic range by reducing compression ratio")

        if crest_factor < 8 and dr_value < 10:
            recommendations.append("Use multiband processing to preserve transients")

        if not recommendations:
            recommendations.append("Dynamic range is well preserved")

        return recommendations

    def get_crest_factor_history(self) -> List[float]:
        """Get crest factor history for temporal analysis"""
        return self.crest_history.copy()

    def reset_history(self) -> None:
        """Reset analysis history"""
        self.crest_history.clear()