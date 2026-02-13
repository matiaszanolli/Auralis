"""
Estimation Operations
~~~~~~~~~~~~~~~~~~~~~

Common signal estimation patterns for quality assessments.

Provides shared estimation functions used across all quality assessors
to ensure consistency and reduce code duplication.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np


class EstimationOperations:
    """Common signal estimation patterns"""

    @staticmethod
    def estimate_thd(audio: np.ndarray, sr: int | None = None,
                     fundamental_idx: int | None = None) -> float:
        """
        Estimate Total Harmonic Distortion

        Simplified THD estimation using high-frequency energy analysis
        based on fundamental and harmonic power ratios.

        Args:
            audio: Audio data (mono or stereo)
            sr: Sample rate (not required for THD estimation)
            fundamental_idx: Optional pre-computed fundamental frequency index

        Returns:
            Estimated THD as ratio (0-1)
        """
        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Use middle section for analysis (avoid silence at start/end)
        mid_start = len(audio_mono) // 4
        mid_end = 3 * len(audio_mono) // 4
        audio_segment = audio_mono[mid_start:mid_end]

        # Compute spectrum
        fft_result = np.fft.rfft(audio_segment)
        magnitude = np.abs(fft_result)

        # Estimate fundamental frequency if not provided
        if fundamental_idx is None:
            fundamental_idx = int(np.argmax(magnitude[10:len(magnitude)//2]) + 10)

        fundamental_power = magnitude[fundamental_idx] ** 2

        # Estimate harmonic power (2nd to 5th harmonics)
        harmonic_power = 0.0
        for i in range(2, 6):  # 2nd to 5th harmonics
            harmonic_idx = min(fundamental_idx * i, len(magnitude) - 1)
            harmonic_power += magnitude[harmonic_idx] ** 2

        # Calculate THD
        if fundamental_power > 0:
            thd = float(np.sqrt(harmonic_power / fundamental_power))
        else:
            thd = 0.0

        return float(thd)

    @staticmethod
    def detect_clipping(audio: np.ndarray,
                       threshold: float = 0.99) -> float:
        """
        Detect audio clipping

        Counts samples at or near digital maximum (0 dBFS).

        Args:
            audio: Audio data
            threshold: Clipping threshold (default 0.99, normalized amplitude)

        Returns:
            Clipping factor (0-1, higher means more clipping)
        """
        clipped_samples = np.sum(np.abs(audio) >= threshold)
        total_samples = audio.size

        clipping_factor = clipped_samples / total_samples if total_samples > 0 else 0.0

        return float(clipping_factor)

    @staticmethod
    def estimate_noise_floor(audio: np.ndarray,
                            silence_threshold: float = 1e-6,
                            percentile: int = 10) -> float:
        """
        Estimate noise floor

        Uses quiet sections of audio to estimate background noise level.

        Args:
            audio: Audio data (mono or stereo)
            silence_threshold: Minimum level considered (default 1e-6)
            percentile: Percentile of amplitude distribution for noise (default 10)

        Returns:
            Noise floor in dB
        """
        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Find quiet sections (bottom percentile by amplitude)
        sorted_abs = np.sort(np.abs(audio_mono))
        noise_samples = sorted_abs[:max(1, len(sorted_abs) // (100 // percentile))]

        if len(noise_samples) > 0:
            noise_level = np.mean(noise_samples)
            noise_level = max(noise_level, silence_threshold)
            noise_floor_db = 20 * np.log10(noise_level)
        else:
            noise_floor_db = -90.0

        return float(noise_floor_db)

    @staticmethod
    def compute_stereo_correlation(left: np.ndarray,
                                  right: np.ndarray) -> float:
        """
        Compute stereo correlation coefficient

        Measures how similar left and right channels are.
        1.0 = identical, 0.0 = uncorrelated, -1.0 = inverse

        Args:
            left: Left channel audio
            right: Right channel audio

        Returns:
            Correlation coefficient (-1 to 1)
        """
        # Ensure same length
        min_len = min(len(left), len(right))
        left = left[:min_len]
        right = right[:min_len]

        # Normalize
        left_norm = left - np.mean(left)
        right_norm = right - np.mean(right)

        # Compute correlation
        numerator = np.sum(left_norm * right_norm)
        denominator = np.sqrt(np.sum(left_norm ** 2) * np.sum(right_norm ** 2))

        if denominator == 0:
            return 0.0

        correlation = numerator / denominator

        return float(np.clip(correlation, -1.0, 1.0))

    @staticmethod
    def estimate_dynamic_range(audio: np.ndarray,
                              sr: int | None = None,
                              frame_duration: float = 0.05) -> float:
        """
        Estimate dynamic range (peak-to-noise)

        Calculates the ratio between loudest and quietest parts.

        Args:
            audio: Audio data
            sr: Sample rate (used for framing, default 44100)
            frame_duration: Duration of analysis frames in seconds

        Returns:
            Dynamic range in dB
        """
        if sr is None:
            sr = 44100

        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Frame audio
        frame_size = int(sr * frame_duration)
        if frame_size < 1:
            frame_size = 1

        rms_values = []
        for i in range(0, len(audio_mono) - frame_size, frame_size):
            frame = audio_mono[i:i + frame_size]
            rms = np.sqrt(np.mean(frame ** 2))
            rms_values.append(rms)

        if not rms_values:
            return 0.0

        peak_rms = np.max(rms_values)
        noise_rms = np.min(rms_values)

        if noise_rms == 0:
            noise_rms = 1e-10

        dynamic_range_db = 20 * np.log10(peak_rms / noise_rms)

        return float(max(0, dynamic_range_db))

    @staticmethod
    def detect_phase_issues(left: np.ndarray,
                           right: np.ndarray) -> float:
        """
        Detect phase alignment issues between stereo channels

        Returns a measure of phase issues from 0 (no issues) to 1 (severe).

        Args:
            left: Left channel audio
            right: Right channel audio

        Returns:
            Phase issue factor (0-1, higher = more issues)
        """
        # Ensure same length
        min_len = min(len(left), len(right))
        left = left[:min_len]
        right = right[:min_len]

        # Compute correlation
        correlation = EstimationOperations.compute_stereo_correlation(left, right)

        # Negative correlation indicates phase issues
        if correlation < 0:
            # Map -1 to 0 as factor 1.0 (severe issue)
            phase_issue_factor = (1 - correlation) / 2  # Maps -1 to 1, 1 to 0
        else:
            # Positive correlation is good
            phase_issue_factor = 0.0

        return float(phase_issue_factor)

    @staticmethod
    def estimate_stereo_width(left: np.ndarray,
                             right: np.ndarray) -> float:
        """
        Estimate stereo width

        Calculates how far apart the stereo channels are.
        0.0 = mono, 1.0 = extremely wide

        Args:
            left: Left channel audio
            right: Right channel audio

        Returns:
            Stereo width factor (0-1)
        """
        # Ensure same length
        min_len = min(len(left), len(right))
        left = left[:min_len]
        right = right[:min_len]

        # Compute side and mid signals
        mid = (left + right) / 2
        side = (left - right) / 2

        # Energy in mid and side
        mid_energy = np.sqrt(np.mean(mid ** 2))
        side_energy = np.sqrt(np.mean(side ** 2))

        if mid_energy == 0:
            return 0.5  # Can't determine, assume moderate

        width = side_energy / (mid_energy + side_energy)

        return float(np.clip(width, 0.0, 1.0))

    @staticmethod
    def estimate_mono_compatibility(left: np.ndarray,
                                   right: np.ndarray) -> float:
        """
        Estimate mono compatibility

        Measures how well the stereo mix translates to mono.
        1.0 = perfect compatibility, 0.0 = severe cancellation

        Args:
            left: Left channel audio
            right: Right channel audio

        Returns:
            Mono compatibility factor (0-1)
        """
        # Ensure same length
        min_len = min(len(left), len(right))
        left = left[:min_len]
        right = right[:min_len]

        # Compute mono mix (sum)
        mono = left + right

        # Compare energy before and after summing
        left_energy = np.sqrt(np.mean(left ** 2))
        right_energy = np.sqrt(np.mean(right ** 2))
        mono_energy = np.sqrt(np.mean(mono ** 2))

        stereo_energy = np.sqrt(left_energy ** 2 + right_energy ** 2)

        if stereo_energy == 0:
            return 1.0

        # Should be close to stereo_energy if compatible
        compatibility = mono_energy / stereo_energy

        return float(np.clip(compatibility, 0.0, 1.0))

    @staticmethod
    def estimate_fundamental_frequency(audio: np.ndarray,
                                      sr: int = 44100) -> tuple[float, int]:
        """
        Estimate fundamental frequency using FFT

        Returns both frequency in Hz and FFT bin index.

        Args:
            audio: Audio data
            sr: Sample rate (default 44100)

        Returns:
            Tuple of (frequency_hz, fft_bin_index)
        """
        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Use middle section
        mid_start = len(audio_mono) // 4
        mid_end = 3 * len(audio_mono) // 4
        audio_segment = audio_mono[mid_start:mid_end]

        # Compute FFT
        fft_result = np.fft.rfft(audio_segment)
        magnitude = np.abs(fft_result)
        frequencies = np.fft.rfftfreq(len(audio_segment), 1 / sr)

        # Find fundamental (skip DC and very low frequencies)
        min_bin = max(1, int(50 * len(audio_segment) / sr))  # 50 Hz minimum
        max_bin = min(len(magnitude), int(2000 * len(audio_segment) / sr))  # 2kHz max

        if min_bin < max_bin:
            magnitude_range = magnitude[min_bin:max_bin]
            fundamental_idx = np.argmax(magnitude_range) + min_bin
        else:
            fundamental_idx = np.argmax(magnitude)

        fundamental_freq = frequencies[fundamental_idx]

        return float(fundamental_freq), int(fundamental_idx)

    @staticmethod
    def detect_excessive_noise(audio: np.ndarray,
                              sr: int = 44100,
                              noise_threshold_db: float = -60) -> bool:
        """
        Detect if audio has excessive noise

        Args:
            audio: Audio data
            sr: Sample rate
            noise_threshold_db: Threshold for "excessive" noise

        Returns:
            True if noise floor is above threshold (bad)
        """
        noise_floor = EstimationOperations.estimate_noise_floor(audio)
        snr = -noise_floor

        return snr < abs(noise_threshold_db)

    @staticmethod
    def detect_excessive_distortion(audio: np.ndarray,
                                   thd_threshold: float = 0.05) -> bool:
        """
        Detect if audio has excessive distortion

        Args:
            audio: Audio data
            thd_threshold: Threshold for "excessive" distortion (default 5%)

        Returns:
            True if THD is above threshold (bad)
        """
        thd = EstimationOperations.estimate_thd(audio)

        return thd > thd_threshold
