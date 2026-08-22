"""
Audio-Specific Metrics and Conversions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Audio-specific metrics for RMS, loudness, and dB conversions.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import librosa
import numpy as np

from ....utils.logging import warning
from .safe_operations import SafeOperations


class AudioMetrics:
    """
    Audio-specific metrics and conversions.
    Consolidates RMS, loudness, and dB conversions.
    """

    @staticmethod
    def rms_to_db(
        rms: np.ndarray,
        ref: float | None = None
    ) -> np.ndarray:
        """
        Convert RMS to dB using librosa standard.

        Args:
            rms: RMS values (can be scalar or array)
            ref: Reference level (default: max of input)

        Returns:
            RMS values in dB

        The default reference normalises to the loudest element, which is what an
        array of per-frame RMS values wants. For a single element that is
        degenerate: the reference IS the value, so the result is identically 0.0
        whatever the input. That silently zeroed three of the seven dimensions of
        every mastering fingerprint (#5099), so the case now warns instead of
        passing quietly. Pass an explicit `ref` (1.0 for dBFS) to silence it.
        """
        rms_array: np.ndarray = np.asarray(rms)

        if ref is None and rms_array.size <= 1:
            warning(
                "rms_to_db() called on a single value with no explicit ref: the "
                "default reference is the input itself, so the result is 0.0 dB "
                "regardless of level. Pass ref=1.0 for dBFS (#5099)."
            )

        ref_val: float = ref if ref is not None else (np.max(np.abs(rms_array)) if np.any(rms_array) else 1.0)

        return librosa.amplitude_to_db(rms_array, ref=ref_val)  # type: ignore[no-any-return]

    @staticmethod
    def loudness_variation(
        rms: np.ndarray,
        ref: float | None = None
    ) -> float:
        """
        Calculate loudness variation (standard deviation of dB values).

        Measures how much loudness varies across frames.

        Args:
            rms: RMS values per frame
            ref: Reference level for dB conversion

        Returns:
            Loudness variation in dB
        """
        rms_db: np.ndarray = AudioMetrics.rms_to_db(rms, ref=ref)
        return float(np.std(rms_db))

    @staticmethod
    def silence_ratio(
        rms: np.ndarray,
        threshold_db: float = -40.0,
        ref: float | None = None
    ) -> float:
        """
        Calculate ratio of silent frames.

        Silent frame = frame with RMS below threshold_db.

        Args:
            rms: RMS values per frame
            threshold_db: dB threshold for silence (default -40 dB)
            ref: Reference level for dB conversion

        Returns:
            Ratio of silent frames in [0, 1]
        """
        rms_db: np.ndarray = AudioMetrics.rms_to_db(rms, ref=ref)
        silent_frames: np.intp = np.sum(rms_db < threshold_db)

        return float(silent_frames / len(rms_db))

    @staticmethod
    def peak_to_rms_ratio(
        audio: np.ndarray
    ) -> float:
        """
        Calculate peak-to-RMS ratio (dynamic range indicator).

        Args:
            audio: Audio signal

        Returns:
            Ratio of peak amplitude to RMS (typically 3-20)
        """
        peak = np.max(np.abs(audio))
        rms_val = np.sqrt(np.mean(audio ** 2))

        if rms_val <= SafeOperations.EPSILON:
            return 1.0

        return float(peak / rms_val)
