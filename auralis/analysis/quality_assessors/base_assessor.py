# -*- coding: utf-8 -*-

"""
Base Assessor
~~~~~~~~~~~~~

Abstract base class for all quality assessors.

Defines the common interface and shared functionality for all quality
assessment implementations across loudness, stereo, distortion, frequency,
and dynamic range metrics.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, List
import numpy as np


class BaseAssessor(ABC):
    """Abstract base class for quality assessors"""

    def __init__(self) -> None:
        """Initialize base assessor"""
        self._cached_analysis: Optional[Dict[str, Any]] = None

    @abstractmethod
    def assess(self, audio_data: np.ndarray, **kwargs: Any) -> float:
        """
        Assess audio quality on a 0-100 scale

        Args:
            audio_data: Audio data to analyze
            **kwargs: Additional assessor-specific parameters

        Returns:
            Quality score (0-100, higher is better)
        """
        pass

    @abstractmethod
    def detailed_analysis(self, audio_data: np.ndarray, **kwargs: Any) -> Dict[str, Any]:
        """
        Perform detailed quality analysis

        Args:
            audio_data: Audio data to analyze
            **kwargs: Additional assessor-specific parameters

        Returns:
            Dictionary with detailed metrics and sub-scores
        """
        pass

    def get_assessment_category(self) -> str:
        """
        Get the assessment category name

        Returns:
            Category name (e.g., "loudness", "stereo", "distortion")
        """
        class_name = self.__class__.__name__
        # Remove "Assessor" suffix and convert to lowercase
        return class_name.replace('Assessor', '').lower()

    def _normalize_audio(self, audio_data: np.ndarray,
                        target_dtype: type[Any] = np.float32) -> np.ndarray:
        """
        Normalize audio to target format

        Ensures audio is in the correct format for analysis.

        Args:
            audio_data: Input audio data
            target_dtype: Target data type (default float32)

        Returns:
            Normalized audio array
        """
        audio: np.ndarray = np.array(audio_data, dtype=target_dtype)

        # Ensure audio is finite
        if not np.all(np.isfinite(audio)):
            # Replace non-finite values with zeros
            audio[~np.isfinite(audio)] = 0.0

        return audio

    def _to_mono(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Convert stereo audio to mono

        Args:
            audio_data: Audio data (mono or stereo)

        Returns:
            Mono audio array
        """
        if audio_data.ndim == 2:
            return np.mean(audio_data, axis=1)  # type: ignore[no-any-return]
        return audio_data

    def _get_stereo_channels(self, audio_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract left and right channels from stereo audio

        Args:
            audio_data: Stereo audio data (2D array or mono)

        Returns:
            Tuple of (left, right) channels. If mono, right is copy of left.
        """
        if audio_data.ndim == 2 and audio_data.shape[1] >= 2:
            return audio_data[:, 0], audio_data[:, 1]
        elif audio_data.ndim == 2 and audio_data.shape[1] == 1:
            return audio_data[:, 0], audio_data[:, 0].copy()
        else:
            return audio_data, audio_data.copy()

    def _validate_audio(self, audio_data: np.ndarray,
                       min_length: int = 44100,
                       max_length: Optional[int] = None) -> bool:
        """
        Validate audio data for analysis

        Args:
            audio_data: Audio data to validate
            min_length: Minimum required audio length (samples)
            max_length: Maximum allowed audio length (samples), None for no limit

        Returns:
            True if audio is valid, False otherwise
        """
        if audio_data is None or len(audio_data) == 0:
            return False

        audio_len = len(audio_data) if audio_data.ndim == 1 else audio_data.shape[0]

        if audio_len < min_length:
            return False

        if max_length is not None and audio_len > max_length:
            return False

        if not np.all(np.isfinite(audio_data)):
            return False

        return True

    def _compute_rms(self, audio_data: np.ndarray,
                    frame_duration: float = 0.05,
                    sr: int = 44100) -> np.ndarray:
        """
        Compute RMS energy over frames

        Args:
            audio_data: Audio data
            frame_duration: Frame duration in seconds
            sr: Sample rate

        Returns:
            Array of RMS values
        """
        if audio_data.ndim == 2:
            audio_mono = np.mean(audio_data, axis=1)
        else:
            audio_mono = audio_data

        frame_size = int(sr * frame_duration)
        if frame_size < 1:
            frame_size = 1

        rms_values = []
        for i in range(0, len(audio_mono) - frame_size, frame_size):
            frame = audio_mono[i:i + frame_size]
            rms = np.sqrt(np.mean(frame ** 2))
            rms_values.append(rms)

        return np.array(rms_values)

    def _compute_spectrum(self, audio_data: np.ndarray,
                         sr: int = 44100,
                         fft_size: int = 2048) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute frequency spectrum

        Args:
            audio_data: Audio data
            sr: Sample rate
            fft_size: FFT size

        Returns:
            Tuple of (frequencies, magnitudes, magnitude_db)
        """
        if audio_data.ndim == 2:
            audio_mono = np.mean(audio_data, axis=1)
        else:
            audio_mono = audio_data

        # Use middle section for analysis
        mid_start = len(audio_mono) // 4
        mid_end = 3 * len(audio_mono) // 4
        audio_segment = audio_mono[mid_start:mid_end]

        # Compute FFT with windowing
        window = np.hanning(len(audio_segment))
        windowed = audio_segment * window

        fft_result = np.fft.rfft(windowed, n=fft_size)
        magnitude = np.abs(fft_result)
        magnitude_db = 20 * np.log10(magnitude + 1e-10)
        frequencies = np.fft.rfftfreq(fft_size, 1 / sr)

        return frequencies, magnitude, magnitude_db

    def _interpolate_score(self, value: float,
                          thresholds: List[float],
                          scores: List[float]) -> float:
        """
        Interpolate score based on thresholds

        Args:
            value: Value to score
            thresholds: List of threshold values (sorted)
            scores: List of corresponding scores

        Returns:
            Interpolated score 0-100
        """
        if value <= thresholds[0]:
            return float(scores[0])

        for i in range(len(thresholds) - 1):
            if thresholds[i] <= value <= thresholds[i + 1]:
                # Linear interpolation
                progress = (value - thresholds[i]) / (thresholds[i + 1] - thresholds[i])
                return float(scores[i] + (scores[i + 1] - scores[i]) * progress)

        return float(scores[-1])

    def clear_cache(self) -> None:
        """Clear any cached analysis results"""
        self._cached_analysis = None
