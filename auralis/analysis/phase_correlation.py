# -*- coding: utf-8 -*-

"""
Phase Correlation Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~

Stereo phase correlation and spatial analysis tools.
"""

import numpy as np
from typing import Dict, Tuple, List
from scipy import signal
from .fingerprint.common_metrics import SafeOperations, MetricUtils


class PhaseCorrelationAnalyzer:
    """Stereo phase correlation and spatial analysis"""

    def __init__(self, sample_rate: int = 44100, analysis_window: float = 0.1):
        self.sample_rate = sample_rate
        self.analysis_window = analysis_window
        self.window_samples = int(analysis_window * sample_rate)

        # Correlation history for temporal analysis
        self.correlation_history = []
        self.max_history_length = 100  # Keep 10 seconds at 10Hz update rate

        # Phase analysis settings
        self.phase_bins = 64
        self.phase_histogram = np.zeros(self.phase_bins)

    def analyze_correlation(self, stereo_audio: np.ndarray) -> Dict:
        """
        Analyze phase correlation of stereo audio

        Args:
            stereo_audio: Stereo audio data [samples, 2]

        Returns:
            Dictionary with correlation analysis results
        """
        if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
            raise ValueError("Input must be stereo audio [samples, 2]")

        left = stereo_audio[:, 0]
        right = stereo_audio[:, 1]

        # Calculate basic correlation coefficient
        correlation = self._calculate_correlation(left, right)

        # Calculate instantaneous phase correlation
        phase_correlation = self._calculate_phase_correlation(left, right)

        # Analyze stereo width
        stereo_width = self._calculate_stereo_width(left, right)

        # Calculate mid/side representation
        mid, side = self._calculate_mid_side(left, right)

        # Analyze phase relationship over time
        phase_stability = self._analyze_phase_stability(left, right)

        # Update correlation history
        self.correlation_history.append(correlation)
        if len(self.correlation_history) > self.max_history_length:
            self.correlation_history.pop(0)

        # Calculate temporal statistics
        correlation_variance = np.var(self.correlation_history) if len(self.correlation_history) > 1 else 0.0
        correlation_trend = self._calculate_correlation_trend()

        return {
            'correlation': float(correlation),
            'phase_correlation': float(phase_correlation),
            'stereo_width': float(stereo_width),
            'phase_stability': float(phase_stability),
            'mid_level': float(np.sqrt(np.mean(mid**2))),
            'side_level': float(np.sqrt(np.mean(side**2))),
            'correlation_variance': float(correlation_variance),
            'correlation_trend': float(correlation_trend),
            'mono_compatibility': float(self._calculate_mono_compatibility(correlation)),
            'stereo_balance': self._calculate_stereo_balance(left, right),
            'phase_coherence': self._calculate_phase_coherence(left, right)
        }

    def _calculate_correlation(self, left: np.ndarray, right: np.ndarray) -> float:
        """Calculate Pearson correlation coefficient"""
        if len(left) == 0 or len(right) == 0:
            return 0.0

        # Normalize signals
        left_norm = left - np.mean(left)
        right_norm = right - np.mean(right)

        left_std = np.std(left_norm)
        right_std = np.std(right_norm)

        if left_std == 0 or right_std == 0:
            return 0.0

        correlation = np.mean(left_norm * right_norm) / (left_std * right_std)
        # Clip correlation to -1 to +1 range using MetricUtils
        return MetricUtils.clip_to_range(correlation, -1.0, 1.0)

    def _calculate_phase_correlation(self, left: np.ndarray, right: np.ndarray) -> float:
        """Calculate phase correlation using analytic signals"""
        # Use Hilbert transform to get analytic signals
        left_analytic = signal.hilbert(left)
        right_analytic = signal.hilbert(right)

        # Calculate instantaneous phases
        left_phase = np.angle(left_analytic)
        right_phase = np.angle(right_analytic)

        # Phase difference
        phase_diff = left_phase - right_phase

        # Unwrap phase differences
        phase_diff_unwrapped = np.unwrap(phase_diff)

        # Calculate phase correlation
        phase_corr = np.abs(np.mean(np.exp(1j * phase_diff_unwrapped)))

        return float(phase_corr)

    def _calculate_stereo_width(self, left: np.ndarray, right: np.ndarray) -> float:
        """Calculate apparent stereo width"""
        # Convert to mid/side
        mid, side = self._calculate_mid_side(left, right)

        # Calculate RMS levels
        mid_rms = np.sqrt(np.mean(mid**2))
        side_rms = np.sqrt(np.mean(side**2))

        # Stereo width based on side/mid ratio
        if mid_rms > 0:
            width = side_rms / mid_rms
        else:
            width = 0.0

        # Normalize 0-2 range to 0-1 (0 = mono, 1 = wide stereo)
        # Use scale_to_range for clearer intent
        return MetricUtils.scale_to_range(width, 0.0, 2.0, 0.0, 1.0)

    def _calculate_mid_side(self, left: np.ndarray, right: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Convert L/R to Mid/Side"""
        mid = (left + right) / 2
        side = (left - right) / 2
        return mid, side

    def _analyze_phase_stability(self, left: np.ndarray, right: np.ndarray) -> float:
        """Analyze how stable the phase relationship is over time"""
        # Divide into small windows and analyze correlation in each
        window_size = self.window_samples // 4
        hop_size = window_size // 2

        correlations = []
        for i in range(0, len(left) - window_size, hop_size):
            left_window = left[i:i + window_size]
            right_window = right[i:i + window_size]

            corr = self._calculate_correlation(left_window, right_window)
            correlations.append(corr)

        if not correlations:
            return 1.0

        # Stability is inverse of variance (lower variance = more stable)
        variance = np.var(correlations)
        stability = 1.0 / (1.0 + variance)

        return float(stability)

    def _calculate_correlation_trend(self) -> float:
        """Calculate trend in correlation over time"""
        if len(self.correlation_history) < 5:
            return 0.0

        # Simple linear regression slope
        x = np.arange(len(self.correlation_history))
        y = np.array(self.correlation_history)

        slope = np.polyfit(x, y, 1)[0]
        return float(slope)

    def _calculate_mono_compatibility(self, correlation: float) -> float:
        """Calculate mono compatibility score"""
        # Mono compatibility is better when correlation is close to +1
        # Worst when correlation is close to -1 (phase cancellation)
        mono_compatibility = (correlation + 1) / 2
        return float(mono_compatibility)

    def _calculate_stereo_balance(self, left: np.ndarray, right: np.ndarray) -> Dict:
        """Calculate stereo balance information"""
        left_rms = np.sqrt(np.mean(left**2))
        right_rms = np.sqrt(np.mean(right**2))

        total_rms = left_rms + right_rms
        if total_rms > 0:
            left_balance = left_rms / total_rms
            right_balance = right_rms / total_rms
        else:
            left_balance = 0.5
            right_balance = 0.5

        # Balance offset from center (0 = perfect balance)
        balance_offset = abs(left_balance - right_balance)

        return {
            'left_level': float(left_rms),
            'right_level': float(right_rms),
            'left_percentage': float(left_balance * 100),
            'right_percentage': float(right_balance * 100),
            'balance_offset': float(balance_offset)
        }

    def _calculate_phase_coherence(self, left: np.ndarray, right: np.ndarray) -> Dict:
        """Calculate frequency-dependent phase coherence"""
        # Use welch method for frequency domain analysis
        f, left_psd = signal.welch(left, self.sample_rate, nperseg=1024)
        f, right_psd = signal.welch(right, self.sample_rate, nperseg=1024)

        # Calculate cross-power spectral density
        f, cross_psd = signal.csd(left, right, self.sample_rate, nperseg=1024)

        # Calculate coherence with safe division
        numerator = np.abs(cross_psd)**2
        denominator = left_psd * right_psd
        coherence = SafeOperations.safe_divide(numerator, denominator, fallback=0.0)

        # Average coherence in frequency bands
        freq_bands = [
            (20, 200, 'low'),
            (200, 2000, 'mid'),
            (2000, 20000, 'high')
        ]

        band_coherence = {}
        for f_low, f_high, band_name in freq_bands:
            mask = (f >= f_low) & (f <= f_high)
            if np.any(mask):
                band_coherence[f'{band_name}_coherence'] = float(np.mean(coherence[mask]))
            else:
                band_coherence[f'{band_name}_coherence'] = 0.0

        return {
            'overall_coherence': float(np.mean(coherence)),
            **band_coherence,
            'frequency_bins': f.tolist(),
            'coherence_spectrum': coherence.tolist()
        }

    def analyze_stereo_field(self, stereo_audio: np.ndarray, num_positions: int = 16) -> Dict:
        """
        Analyze stereo field positioning

        Args:
            stereo_audio: Stereo audio data
            num_positions: Number of positions across stereo field

        Returns:
            Dictionary with stereo field analysis
        """
        if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
            raise ValueError("Input must be stereo audio [samples, 2]")

        left = stereo_audio[:, 0]
        right = stereo_audio[:, 1]

        # Calculate energy at different pan positions
        positions = np.linspace(-1, 1, num_positions)  # -1 = full left, +1 = full right
        position_energy = []

        for pos in positions:
            # Calculate what the signal would sound like at this position
            if pos <= 0:  # Left side
                left_gain = 1.0
                right_gain = 1.0 + pos  # pos is negative, so this reduces right
            else:  # Right side
                left_gain = 1.0 - pos  # pos is positive, so this reduces left
                right_gain = 1.0

            # Apply panning gains
            panned_left = left * left_gain
            panned_right = right * right_gain

            # Calculate energy at this position
            energy = np.mean((panned_left + panned_right)**2)
            position_energy.append(energy)

        # Normalize energies using safe division
        max_energy = max(position_energy) if position_energy else 1.0
        if max_energy > 0:
            # Use numpy array for vectorized normalization with MetricUtils
            position_energy_array = np.array(position_energy)
            normalized = position_energy_array / max_energy
            position_energy = normalized.tolist()

        # Find center of mass (stereo center)
        if sum(position_energy) > 0:
            center_of_mass = sum(pos * energy for pos, energy in zip(positions, position_energy)) / sum(position_energy)
        else:
            center_of_mass = 0.0

        # Calculate stereo spread
        if sum(position_energy) > 0:
            spread = np.sqrt(sum((pos - center_of_mass)**2 * energy for pos, energy in zip(positions, position_energy)) / sum(position_energy))
        else:
            spread = 0.0

        return {
            'positions': positions.tolist(),
            'position_energy': position_energy,
            'stereo_center': float(center_of_mass),
            'stereo_spread': float(spread),
            'field_width': float(spread * 2),  # Total width of stereo field
            'left_weighted': float(center_of_mass < -0.1),
            'right_weighted': float(center_of_mass > 0.1),
            'centered': float(abs(center_of_mass) < 0.1)
        }

    def get_correlation_history(self) -> List[float]:
        """Get correlation history for temporal visualization"""
        return self.correlation_history.copy()

    def reset_history(self):
        """Reset correlation history"""
        self.correlation_history.clear()