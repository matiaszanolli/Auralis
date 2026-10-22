"""
Dynamic Range Analysis
~~~~~~~~~~~~~~~~~~~~~

Comprehensive dynamic range measurement and analysis tools.
"""

from typing import Any

import numpy as np
from scipy import signal

from auralis.analysis.fingerprint.metrics import AudioMetrics
from ..dsp.utils.conversion import amplitude_to_db, peak_db
from .dynamic_range_dynamics import DynamicsMetricsMixin

class DynamicRangeAnalyzer(DynamicsMetricsMixin):
    """Comprehensive dynamic range analysis"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

        # Analysis parameters
        self.rms_window_size = int(0.05 * sample_rate)  # 50ms RMS window
        self.peak_hold_time = int(0.5 * sample_rate)    # 500ms peak hold
        self.gate_threshold = -70.0  # dBFS gating threshold

        # Crest factor analysis
        self.crest_history: list[float] = []
        self.max_crest_history = 200  # Keep 10 seconds at 20Hz

    def analyze_dynamic_range(self, audio_data: np.ndarray) -> dict[str, Any]:
        """
        Comprehensive dynamic range analysis

        Args:
            audio_data: Audio data (mono or stereo)

        Returns:
            Dictionary with dynamic range metrics
        """
        if audio_data.ndim == 2:
            # For stereo, ravel all channel samples to compute true stereo RMS
            # instead of averaging channels first (which underestimates by up
            # to 3 dB for uncorrelated content — see #2579).
            audio_mono = audio_data.ravel()
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
        return peak_db(audio)

    def _calculate_rms_level(self, audio: np.ndarray) -> float:
        """Calculate RMS level in dBFS"""
        return amplitude_to_db(np.sqrt(np.mean(audio**2)))

    def _calculate_dr_value(self, audio: np.ndarray) -> float:
        """
        Dynamic Range (DR) value per the Pleasurize Music Foundation / TT
        DR-meter algorithm.

        #5222: the previous implementation was self-described as "simplified"
        and computed 95th-percentile block peak minus mean block RMS, which is
        a crest-factor-like number, not DR. That mattered even though the
        value is advisory-only, because everything reading it here —
        `_categorize_dynamic_range`'s 20/14/10/7/4 bands and
        `_assess_loudness_war`'s `dr_value < 7` / `< 10` tests — is written
        against the real DR scale, where DR14 is a well-mastered record and
        DR7 is a heavily limited one.

        The algorithm: split into 3 s blocks; per block take
        ``rms = sqrt(2 * mean(x**2))`` (the factor 2 is part of the
        definition — it normalises a full-scale sine to 0 dB so a steady tone
        measures DR 0 rather than its 3 dB crest) and the block peak; then
        ``DR = 20*log10(peak2 / rms_top20)`` where ``rms_top20`` is the
        quadratic mean of the loudest 20 % of blocks by RMS and ``peak2`` is
        the second-highest block peak (the highest is discarded so a single
        sample-level tick cannot inflate the result).

        Args:
            audio: Mono audio (callers ravel stereo before calling).

        Returns:
            DR value in dB, 0.0 for input shorter than one 3 s block.
        """
        block_samples = int(3.0 * self.sample_rate)

        if len(audio) < block_samples:
            return 0.0

        # Whole blocks only. The old stride loop ran to `len - block_samples`
        # exclusive, so it silently dropped the final complete block (and saw
        # just one block for exactly-two-blocks input).
        n_blocks = len(audio) // block_samples
        blocks = audio[:n_blocks * block_samples].astype(np.float64).reshape(
            n_blocks, block_samples
        )

        block_rms = np.sqrt(2.0 * np.mean(blocks ** 2, axis=1))
        block_peaks = np.max(np.abs(blocks), axis=1)

        peaks_desc = np.sort(block_peaks)[::-1]
        peak2 = peaks_desc[1] if n_blocks >= 2 else peaks_desc[0]

        n_top = max(1, int(round(0.2 * n_blocks)))
        rms_top = float(np.sqrt(np.mean(np.sort(block_rms)[::-1][:n_top] ** 2)))

        if rms_top <= 0.0 or peak2 <= 0.0:
            return 0.0

        return max(0.0, float(20.0 * np.log10(peak2 / rms_top)))

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

    def _analyze_rms_variation(self, audio: np.ndarray) -> dict[str, Any]:
        """Analyze RMS variation over time"""
        # Calculate RMS in sliding windows
        hop_size = self.rms_window_size // 2
        rms_values = []

        for i in range(0, len(audio) - self.rms_window_size, hop_size):
            window = audio[i:i + self.rms_window_size]
            window_rms = np.sqrt(np.mean(window**2))
            if window_rms > 0:  # silent windows are skipped, not recorded as -inf
                rms_values.append(amplitude_to_db(window_rms))

        if not rms_values:
            return {
                'rms_range_db': 0.0,
                'rms_variance': 0.0,
                'rms_stability': 1.0
            }

        rms_array = np.array(rms_values)
        finite_rms = rms_array[np.isfinite(rms_array)]

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

    def _analyze_peak_distribution(self, audio: np.ndarray) -> dict[str, Any]:
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

    def _get_dynamic_range_recommendations(self, crest_factor: float, dr_value: float) -> list[str]:
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

    def get_crest_factor_history(self) -> list[float]:
        """Get crest factor history for temporal analysis"""
        return self.crest_history.copy()

    def reset_history(self) -> None:
        """Reset analysis history"""
        self.crest_history.clear()