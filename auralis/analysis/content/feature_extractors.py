# -*- coding: utf-8 -*-

"""
Feature Extractors
~~~~~~~~~~~~~~~~~~

Audio feature extraction methods for content analysis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks
from typing import Dict, Any

from ...dsp.unified import (
    spectral_centroid, spectral_rolloff, zero_crossing_rate,
    crest_factor, tempo_estimate, rms, energy_profile
)


class FeatureExtractor:
    """Extract audio features for content analysis"""

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize feature extractor

        Args:
            sample_rate: Audio sample rate
        """
        self.sample_rate = sample_rate

    def calculate_dynamic_range(self, audio: np.ndarray) -> float:
        """Calculate dynamic range in dB"""
        window_size = int(0.5 * self.sample_rate)  # 500ms windows
        hop_size = window_size // 2

        rms_values = []
        for i in range(0, len(audio) - window_size, hop_size):
            window = audio[i:i + window_size]
            rms_val = np.sqrt(np.mean(window ** 2))
            if rms_val > 1e-6:  # Avoid silence
                rms_values.append(rms_val)

        if len(rms_values) < 2:
            return 20.0

        rms_values = np.array(rms_values)
        loud_level = np.percentile(rms_values, 95)
        quiet_level = np.percentile(rms_values, 10)

        if quiet_level > 0:
            return 20 * np.log10(loud_level / quiet_level)
        else:
            return 20.0

    def calculate_spectral_spread(self, audio: np.ndarray) -> float:
        """Calculate spectral spread (bandwidth)"""
        fft_result = fft(audio[:8192])  # Use first 8192 samples
        magnitude = np.abs(fft_result[:4096])
        freqs = fftfreq(8192, 1/self.sample_rate)[:4096]

        # Calculate centroid
        if np.sum(magnitude) > 0:
            centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
            # Calculate spread around centroid
            spread = np.sqrt(np.sum(((freqs - centroid) ** 2) * magnitude) / np.sum(magnitude))
            return spread
        return 1000.0  # Default spread

    def calculate_spectral_flux(self, audio: np.ndarray) -> float:
        """Calculate spectral flux (rate of spectral change)"""
        window_size = 2048
        hop_size = 1024

        flux_values = []
        prev_spectrum = None

        for i in range(0, len(audio) - window_size, hop_size):
            window = audio[i:i + window_size]
            spectrum = np.abs(fft(window)[:window_size//2])

            if prev_spectrum is not None:
                flux = np.sum(np.maximum(0, spectrum - prev_spectrum))
                flux_values.append(flux)

            prev_spectrum = spectrum

        return np.mean(flux_values) if flux_values else 0.0

    def estimate_attack_time(self, audio: np.ndarray) -> float:
        """Estimate average attack time in milliseconds"""
        # Simple onset detection and attack time estimation
        energy = energy_profile(audio, window_size=512)

        # Find onsets (energy increases)
        onset_threshold = np.mean(energy) + np.std(energy)
        onsets = []

        for i in range(1, len(energy) - 1):
            if (energy[i] > onset_threshold and
                energy[i] > energy[i-1] and
                energy[i] > energy[i+1]):
                onsets.append(i)

        if len(onsets) < 2:
            return 50.0  # Default attack time

        # Estimate attack times around onsets
        attack_times = []
        hop_size = 256  # For energy profile calculation

        for onset_idx in onsets[:10]:  # Analyze first 10 onsets
            start_sample = onset_idx * hop_size
            if start_sample + 2048 < len(audio):
                segment = audio[start_sample:start_sample + 2048]

                # Find 10% to 90% rise time
                envelope = np.abs(segment)
                max_val = np.max(envelope)

                if max_val > 0:
                    ten_percent = max_val * 0.1
                    ninety_percent = max_val * 0.9

                    ten_idx = np.where(envelope >= ten_percent)[0]
                    ninety_idx = np.where(envelope >= ninety_percent)[0]

                    if len(ten_idx) > 0 and len(ninety_idx) > 0:
                        attack_samples = ninety_idx[0] - ten_idx[0]
                        attack_time_ms = (attack_samples / self.sample_rate) * 1000
                        attack_times.append(attack_time_ms)

        return np.mean(attack_times) if attack_times else 50.0

    def estimate_fundamental_frequency(self, audio: np.ndarray) -> float:
        """Estimate fundamental frequency using autocorrelation"""
        # Use middle section of audio
        start = len(audio) // 4
        end = 3 * len(audio) // 4
        segment = audio[start:end]

        if len(segment) < 4096:
            return 0.0

        # Autocorrelation
        autocorr = np.correlate(segment, segment, mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        # Find peaks in autocorrelation
        min_period = int(self.sample_rate / 800)  # 800 Hz max
        max_period = int(self.sample_rate / 80)   # 80 Hz min

        if max_period >= len(autocorr):
            return 0.0

        search_range = autocorr[min_period:max_period]
        if len(search_range) == 0:
            return 0.0

        peak_idx = np.argmax(search_range) + min_period
        fundamental = self.sample_rate / peak_idx

        return fundamental if 80 <= fundamental <= 800 else 0.0

    def calculate_harmonic_ratio(self, audio: np.ndarray) -> float:
        """Calculate harmonic to noise ratio"""
        fft_result = fft(audio[:8192])
        magnitude = np.abs(fft_result[:4096])

        # Find peaks (harmonics)
        peaks, _ = find_peaks(magnitude, height=np.max(magnitude) * 0.1)

        if len(peaks) == 0:
            return 0.0

        # Sum energy at peaks (harmonic) vs total energy
        harmonic_energy = np.sum(magnitude[peaks])
        total_energy = np.sum(magnitude)

        if total_energy > 0:
            return harmonic_energy / total_energy
        else:
            return 0.0

    def calculate_inharmonicity(self, audio: np.ndarray) -> float:
        """Calculate inharmonicity (deviation from perfect harmonic series)"""
        fundamental = self.estimate_fundamental_frequency(audio)

        if fundamental == 0:
            return 1.0  # Maximum inharmonicity for non-tonal content

        fft_result = fft(audio[:8192])
        magnitude = np.abs(fft_result[:4096])
        freqs = fftfreq(8192, 1/self.sample_rate)[:4096]

        # Expected harmonic frequencies
        harmonics = [fundamental * i for i in range(1, 11)]  # First 10 harmonics

        deviations = []
        for harmonic_freq in harmonics:
            if harmonic_freq < self.sample_rate / 2:
                # Find closest frequency bin
                closest_idx = np.argmin(np.abs(freqs - harmonic_freq))

                # Look for peak near expected harmonic
                search_range = 10  # bins
                start_idx = max(0, closest_idx - search_range)
                end_idx = min(len(magnitude), closest_idx + search_range)

                local_peak_idx = np.argmax(magnitude[start_idx:end_idx]) + start_idx
                actual_freq = freqs[local_peak_idx]

                if magnitude[local_peak_idx] > np.max(magnitude) * 0.05:
                    deviation = abs(actual_freq - harmonic_freq) / harmonic_freq
                    deviations.append(deviation)

        return np.mean(deviations) if deviations else 1.0

    def calculate_rhythm_strength(self, audio: np.ndarray) -> float:
        """Calculate rhythmic strength"""
        # Calculate onset strength
        onset_envelope = self.calculate_onset_strength(audio)

        # Autocorrelation of onset envelope to find rhythmic patterns
        autocorr = np.correlate(onset_envelope, onset_envelope, mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        # Look for peaks corresponding to beat periods
        hop_size = 512
        fps = self.sample_rate / hop_size

        min_bpm = 60
        max_bpm = 200
        min_period = int(60 * fps / max_bpm)
        max_period = int(60 * fps / min_bpm)

        if max_period >= len(autocorr):
            return 0.0

        rhythm_range = autocorr[min_period:max_period]
        rhythm_strength = np.max(rhythm_range) / (np.mean(autocorr) + 1e-6)

        return min(rhythm_strength / 10.0, 1.0)  # Normalize

    def calculate_beat_consistency(self, audio: np.ndarray) -> float:
        """Calculate beat consistency (regularity)"""
        onset_times = self.detect_onsets(audio)

        if len(onset_times) < 4:
            return 0.0

        # Calculate inter-onset intervals
        intervals = np.diff(onset_times)

        if len(intervals) < 2:
            return 0.0

        # Measure consistency as inverse of coefficient of variation
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)

        if mean_interval > 0:
            consistency = 1.0 / (1.0 + std_interval / mean_interval)
            return consistency
        else:
            return 0.0

    def calculate_onset_strength(self, audio: np.ndarray) -> np.ndarray:
        """Calculate onset strength envelope"""
        window_size = 1024
        hop_size = 512

        onset_strength = []

        for i in range(0, len(audio) - window_size, hop_size):
            window = audio[i:i + window_size]
            spectrum = np.abs(fft(window)[:window_size//2])
            onset_strength.append(np.sum(spectrum))

        return np.array(onset_strength)

    def detect_onsets(self, audio: np.ndarray) -> np.ndarray:
        """Detect onset times in audio"""
        onset_envelope = self.calculate_onset_strength(audio)

        # Differentiate to find increases
        onset_diff = np.diff(onset_envelope)
        onset_diff = np.maximum(0, onset_diff)  # Positive differences only

        # Threshold
        threshold = np.mean(onset_diff) + 2 * np.std(onset_diff)
        onset_indices = np.where(onset_diff > threshold)[0]

        # Convert to time
        hop_size = 512
        onset_times = onset_indices * hop_size / self.sample_rate

        return onset_times


def create_feature_extractor(sample_rate: int = 44100) -> FeatureExtractor:
    """
    Factory function to create feature extractor

    Args:
        sample_rate: Audio sample rate

    Returns:
        Configured FeatureExtractor instance
    """
    return FeatureExtractor(sample_rate)
