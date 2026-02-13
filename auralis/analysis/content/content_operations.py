"""
Content Analysis Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shared operations for audio content analysis including feature extraction,
genre classification, and mood analysis.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

import numpy as np
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks

from ...dsp.unified import energy_profile
from ..fingerprint.common_metrics import AggregationUtils


class ContentAnalysisOperations:
    """Shared operations for content analysis and feature extraction"""

    @staticmethod
    def calculate_dynamic_range(audio: np.ndarray, sample_rate: int = 44100) -> float:
        """
        Calculate dynamic range in dB

        Args:
            audio: Audio data
            sample_rate: Sample rate in Hz

        Returns:
            Dynamic range in dB
        """
        window_size = int(0.5 * sample_rate)  # 500ms windows
        hop_size = window_size // 2

        rms_values_list: list[Any] = []
        for i in range(0, len(audio) - window_size, hop_size):
            window = audio[i:i + window_size]
            rms_val = np.sqrt(np.mean(window ** 2))
            if rms_val > 1e-6:  # Avoid silence
                rms_values_list.append(rms_val)

        if len(rms_values_list) < 2:
            return 20.0

        rms_values = np.array(rms_values_list)
        loud_level = np.percentile(rms_values, 95)
        quiet_level = np.percentile(rms_values, 10)

        if quiet_level > 0:
            return float(20 * np.log10(loud_level / quiet_level))
        else:
            return 20.0

    @staticmethod
    def calculate_spectral_spread(audio: np.ndarray, sample_rate: int = 44100) -> float:
        """
        Calculate spectral spread (bandwidth)

        Args:
            audio: Audio data
            sample_rate: Sample rate in Hz

        Returns:
            Spectral spread in Hz
        """
        fft_result = fft(audio[:8192])  # Use first 8192 samples
        magnitude = np.abs(fft_result[:4096])
        freqs = fftfreq(8192, 1/sample_rate)[:4096]

        # Calculate centroid
        if np.sum(magnitude) > 0:
            centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
            # Calculate spread around centroid
            spread = np.sqrt(np.sum(((freqs - centroid) ** 2) * magnitude) / np.sum(magnitude))
            return float(spread)
        return 1000.0  # Default spread

    @staticmethod
    def calculate_spectral_flux(audio: np.ndarray) -> float:
        """
        Calculate spectral flux (rate of spectral change)

        Args:
            audio: Audio data

        Returns:
            Average spectral flux
        """
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

        # Aggregate spectral flux values using mean
        if flux_values:
            flux_array = np.array(flux_values)
            return AggregationUtils.aggregate_frames_to_track(flux_array, method='mean')
        else:
            return 0.0

    @staticmethod
    def estimate_attack_time(audio: np.ndarray, sample_rate: int = 44100) -> float:
        """
        Estimate average attack time in milliseconds

        Args:
            audio: Audio data
            sample_rate: Sample rate in Hz

        Returns:
            Attack time in milliseconds
        """
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
                        attack_time_ms = (attack_samples / sample_rate) * 1000
                        attack_times.append(attack_time_ms)

        # Aggregate attack times using mean
        if attack_times:
            attack_times_array = np.array(attack_times)
            return AggregationUtils.aggregate_frames_to_track(attack_times_array, method='mean')
        else:
            return 50.0

    @staticmethod
    def estimate_fundamental_frequency(audio: np.ndarray, sample_rate: int = 44100) -> float:
        """
        Estimate fundamental frequency using autocorrelation

        Args:
            audio: Audio data
            sample_rate: Sample rate in Hz

        Returns:
            Fundamental frequency in Hz
        """
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
        min_period = int(sample_rate / 800)  # 800 Hz max
        max_period = int(sample_rate / 80)   # 80 Hz min

        if max_period >= len(autocorr):
            return 0.0

        search_range = autocorr[min_period:max_period]
        if len(search_range) == 0:
            return 0.0

        peak_idx = np.argmax(search_range) + min_period
        fundamental = sample_rate / peak_idx

        return fundamental if 80 <= fundamental <= 800 else 0.0

    @staticmethod
    def calculate_harmonic_ratio(audio: np.ndarray) -> float:
        """
        Calculate harmonic to noise ratio

        Args:
            audio: Audio data

        Returns:
            Harmonic ratio (0-1)
        """
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
            return float(harmonic_energy / total_energy)
        else:
            return 0.0

    @staticmethod
    def calculate_inharmonicity(audio: np.ndarray, sample_rate: int = 44100) -> float:
        """
        Calculate inharmonicity (deviation from perfect harmonic series)

        Args:
            audio: Audio data
            sample_rate: Sample rate in Hz

        Returns:
            Inharmonicity value (0-1)
        """
        fundamental = ContentAnalysisOperations.estimate_fundamental_frequency(audio, sample_rate)

        if fundamental == 0:
            return 1.0  # Maximum inharmonicity for non-tonal content

        fft_result = fft(audio[:8192])
        magnitude = np.abs(fft_result[:4096])
        freqs = fftfreq(8192, 1/sample_rate)[:4096]

        # Expected harmonic frequencies
        harmonics = [fundamental * i for i in range(1, 11)]  # First 10 harmonics

        deviations: list[Any] = []
        for harmonic_freq in harmonics:
            if harmonic_freq < sample_rate / 2:
                # Find closest frequency bin
                closest_idx = int(np.argmin(np.abs(freqs - harmonic_freq)))

                # Look for peak near expected harmonic
                search_range = 10  # bins
                start_idx = int(max(0, closest_idx - search_range))
                end_idx = int(min(len(magnitude), closest_idx + search_range))

                local_peak_idx = int(np.argmax(magnitude[start_idx:end_idx])) + start_idx
                actual_freq = freqs[local_peak_idx]

                if magnitude[local_peak_idx] > np.max(magnitude) * 0.05:
                    deviation = abs(actual_freq - harmonic_freq) / harmonic_freq
                    deviations.append(deviation)

        # Aggregate harmonic deviations using mean
        if deviations:
            deviations_array = np.array(deviations)
            return AggregationUtils.aggregate_frames_to_track(deviations_array, method='mean')
        else:
            return 1.0

    @staticmethod
    def calculate_rhythm_strength(audio: np.ndarray, sample_rate: int = 44100) -> float:
        """
        Calculate rhythmic strength

        Args:
            audio: Audio data
            sample_rate: Sample rate in Hz

        Returns:
            Rhythm strength (0-1)
        """
        # Calculate onset strength
        onset_envelope = ContentAnalysisOperations.calculate_onset_strength(audio)

        # Autocorrelation of onset envelope to find rhythmic patterns
        autocorr = np.correlate(onset_envelope, onset_envelope, mode='full')
        autocorr = autocorr[len(autocorr)//2:]

        # Look for peaks corresponding to beat periods
        hop_size = 512
        fps = sample_rate / hop_size

        min_bpm = 60
        max_bpm = 200
        min_period = int(60 * fps / max_bpm)
        max_period = int(60 * fps / min_bpm)

        if max_period >= len(autocorr):
            return 0.0

        rhythm_range = autocorr[min_period:max_period]
        rhythm_strength = np.max(rhythm_range) / (np.mean(autocorr) + 1e-6)

        return float(min(rhythm_strength / 10.0, 1.0))

    @staticmethod
    def calculate_beat_consistency(audio: np.ndarray, sample_rate: int = 44100) -> float:
        """
        Calculate beat consistency (regularity)

        Args:
            audio: Audio data
            sample_rate: Sample rate in Hz

        Returns:
            Beat consistency (0-1)
        """
        onset_times = ContentAnalysisOperations.detect_onsets(audio, sample_rate)

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
            return float(consistency)
        else:
            return 0.0

    @staticmethod
    def calculate_onset_strength(audio: np.ndarray) -> np.ndarray:
        """
        Calculate onset strength envelope

        Args:
            audio: Audio data

        Returns:
            Onset strength array
        """
        window_size = 1024
        hop_size = 512

        onset_strength = []

        for i in range(0, len(audio) - window_size, hop_size):
            window = audio[i:i + window_size]
            spectrum = np.abs(fft(window)[:window_size//2])
            onset_strength.append(np.sum(spectrum))

        return np.array(onset_strength)

    @staticmethod
    def detect_onsets(audio: np.ndarray, sample_rate: int = 44100) -> np.ndarray:
        """
        Detect onset times in audio

        Args:
            audio: Audio data
            sample_rate: Sample rate in Hz

        Returns:
            Array of onset times in seconds
        """
        onset_envelope = ContentAnalysisOperations.calculate_onset_strength(audio)

        # Differentiate to find increases
        onset_diff = np.diff(onset_envelope)
        onset_diff = np.maximum(0, onset_diff)  # Positive differences only

        # Threshold
        threshold = np.mean(onset_diff) + 2 * np.std(onset_diff)
        onset_indices = np.where(onset_diff > threshold)[0]

        # Convert to time
        hop_size = 512
        onset_times = onset_indices * hop_size / sample_rate

        return onset_times
