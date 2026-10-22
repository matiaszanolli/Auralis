"""
Estimation Operations
~~~~~~~~~~~~~~~~~~~~~

Common signal estimation patterns for quality assessments.

Provides shared estimation functions used across all quality assessors
to ensure consistency and reduce code duplication.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


import numpy as np

from ....dsp.utils.audio_info import to_mono


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
        audio_mono = to_mono(audio)

        # Use middle section for analysis (avoid silence at start/end)
        mid_start = len(audio_mono) // 4
        mid_end = 3 * len(audio_mono) // 4
        audio_segment = audio_mono[mid_start:mid_end]

        # #4996: len(audio_mono) in {0, 1} yields an empty middle section,
        # and np.fft.rfft raises ValueError on a 0-length array. THD is
        # undefined for degenerate input — same sentinel as the "no valid
        # harmonics in range" case below.
        if len(audio_segment) == 0:
            return 0.0

        # Compute spectrum
        fft_result = np.fft.rfft(audio_segment)
        magnitude = np.abs(fft_result)

        # Estimate fundamental frequency if not provided
        if fundamental_idx is None:
            fundamental_idx = int(np.argmax(magnitude[10:len(magnitude)//2]) + 10)

        fundamental_power = magnitude[fundamental_idx] ** 2

        # Estimate harmonic power (2nd to 5th harmonics).
        # #3678: previously all out-of-range harmonic indices were clamped
        # to `len(magnitude) - 1` (the Nyquist bin), so for a fundamental
        # in the upper half of the spectrum harmonic_power collapsed to
        # `(n_harmonics_out_of_range) * magnitude[Nyquist]^2` — meaningless
        # for bright content (cymbals, distorted guitar) and dominating
        # the DistortionAssessor weight (40% of quality score).
        # Fix: only include harmonics whose theoretical index falls
        # within the valid spectrum (≤ len(magnitude) - 1).
        max_bin = len(magnitude) - 1
        harmonic_power = 0.0
        n_harmonics_used = 0
        for i in range(2, 6):  # 2nd to 5th harmonics
            harmonic_idx = fundamental_idx * i
            if harmonic_idx <= max_bin:
                harmonic_power += magnitude[harmonic_idx] ** 2
                n_harmonics_used += 1

        # Calculate THD.
        # If no harmonics are within range (fundamental near Nyquist),
        # return 0 — THD is undefined when the spectrum cannot contain
        # any harmonics of the detected fundamental.
        if fundamental_power > 0 and n_harmonics_used > 0:
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
        audio_mono = to_mono(audio)

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
