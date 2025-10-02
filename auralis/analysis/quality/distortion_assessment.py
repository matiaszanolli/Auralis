# -*- coding: utf-8 -*-

"""
Distortion Assessment
~~~~~~~~~~~~~~~~~~~~

Assess audio distortion and noise levels

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict


class DistortionAssessor:
    """Assess distortion and noise quality"""

    def assess(self, audio_data: np.ndarray) -> float:
        """
        Assess distortion levels (0-100)

        Args:
            audio_data: Audio data to analyze

        Returns:
            Quality score (0-100, higher is better)
        """
        # Calculate THD+N estimation
        thd = self._estimate_thd(audio_data)

        # Calculate clipping detection
        clipping_factor = self._detect_clipping(audio_data)

        # Calculate noise floor
        noise_floor = self._estimate_noise_floor(audio_data)

        # Individual scores
        thd_score = self._score_thd(thd)
        clipping_score = max(0, 100 - clipping_factor * 1000)
        noise_score = self._score_noise_floor(noise_floor)

        # Combined score (weighted average)
        total_score = (thd_score * 0.4 + clipping_score * 0.3 + noise_score * 0.3)

        return float(total_score)

    def _estimate_thd(self, audio_data: np.ndarray) -> float:
        """
        Estimate Total Harmonic Distortion

        Simplified THD estimation using high-frequency energy analysis

        Args:
            audio_data: Audio data

        Returns:
            Estimated THD as ratio (0-1)
        """
        if audio_data.ndim == 2:
            audio_mono = np.mean(audio_data, axis=1)
        else:
            audio_mono = audio_data

        # Use middle section for analysis
        mid_start = len(audio_mono) // 4
        mid_end = 3 * len(audio_mono) // 4
        audio_segment = audio_mono[mid_start:mid_end]

        # Compute spectrum
        fft_result = np.fft.rfft(audio_segment)
        magnitude = np.abs(fft_result)

        # Estimate fundamental frequency (simplified)
        fundamental_idx = np.argmax(magnitude[10:len(magnitude)//2]) + 10
        fundamental_power = magnitude[fundamental_idx] ** 2

        # Estimate harmonic power (simplified)
        harmonic_power = 0
        for i in range(2, 6):  # 2nd to 5th harmonics
            harmonic_idx = min(fundamental_idx * i, len(magnitude) - 1)
            harmonic_power += magnitude[harmonic_idx] ** 2

        # Calculate THD
        if fundamental_power > 0:
            thd = np.sqrt(harmonic_power / fundamental_power)
        else:
            thd = 0.0

        return float(thd)

    def _detect_clipping(self, audio_data: np.ndarray) -> float:
        """
        Detect audio clipping

        Args:
            audio_data: Audio data

        Returns:
            Clipping factor (0-1, higher means more clipping)
        """
        # Count samples very close to digital maximum
        clipping_threshold = 0.99
        clipped_samples = np.sum(np.abs(audio_data) >= clipping_threshold)
        total_samples = audio_data.size

        clipping_factor = clipped_samples / total_samples

        return float(clipping_factor)

    def _estimate_noise_floor(self, audio_data: np.ndarray) -> float:
        """
        Estimate noise floor

        Args:
            audio_data: Audio data

        Returns:
            Noise floor in dB
        """
        if audio_data.ndim == 2:
            audio_mono = np.mean(audio_data, axis=1)
        else:
            audio_mono = audio_data

        # Find quiet sections (bottom 10% by amplitude)
        sorted_abs = np.sort(np.abs(audio_mono))
        noise_samples = sorted_abs[:len(sorted_abs) // 10]

        if len(noise_samples) > 0:
            noise_level = np.mean(noise_samples)
            noise_floor_db = 20 * np.log10(max(noise_level, 1e-10))
        else:
            noise_floor_db = -90.0

        return float(noise_floor_db)

    def _score_thd(self, thd: float) -> float:
        """Score THD (lower is better)"""
        if thd < 0.001:  # < 0.1%
            return 100.0
        elif thd < 0.01:  # < 1%
            return 80 + (0.01 - thd) * 20 / 0.009
        elif thd < 0.05:  # < 5%
            return 40 + (0.05 - thd) * 40 / 0.04
        else:
            return max(0, 40 - thd * 40 / 0.05)

    def _score_noise_floor(self, noise_floor_db: float) -> float:
        """Score noise floor (higher SNR is better)"""
        snr_db = -noise_floor_db
        if snr_db > 90:
            return 100.0
        elif snr_db > 60:
            return 70 + (snr_db - 60) * 30 / 30
        else:
            return snr_db * 70 / 60

    def detailed_analysis(self, audio_data: np.ndarray) -> Dict:
        """
        Perform detailed distortion analysis

        Args:
            audio_data: Audio data to analyze

        Returns:
            Dictionary with detailed distortion metrics
        """
        thd = self._estimate_thd(audio_data)
        clipping_factor = self._detect_clipping(audio_data)
        noise_floor = self._estimate_noise_floor(audio_data)

        return {
            'thd': float(thd),
            'thd_percent': float(thd * 100),
            'clipping_factor': float(clipping_factor),
            'clipping_percent': float(clipping_factor * 100),
            'noise_floor_db': float(noise_floor),
            'snr_db': float(-noise_floor),
            'has_clipping': clipping_factor > 0.001,
            'excessive_distortion': thd > 0.05,
            'high_noise': noise_floor > -60
        }
