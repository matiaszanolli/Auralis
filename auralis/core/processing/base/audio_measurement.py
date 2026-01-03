# -*- coding: utf-8 -*-

"""
Audio Measurement
~~~~~~~~~~~~~~~~~

Audio measurement utilities for processing pipelines.
Provides AudioMeasurement and MeasurementUtilities classes.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Optional

import numpy as np

from ....dsp.basic import rms
from ....utils.logging import debug
from .db_conversion import DBConversion


class AudioMeasurement:
    """Represents audio measurements (peak, RMS, crest factor)"""

    def __init__(self, peak: float, rms_val: float, peak_db: Optional[float] = None, rms_db: Optional[float] = None) -> None:
        """
        Initialize audio measurement

        Args:
            peak: Peak amplitude (linear, 0-1)
            rms_val: RMS level (linear, 0-1)
            peak_db: Peak in dB (optional, calculated if not provided)
            rms_db: RMS in dB (optional, calculated if not provided)
        """
        self.peak: float = peak
        self.rms: float = rms_val
        self.peak_db: float = peak_db if peak_db is not None else (20 * np.log10(peak) if peak > 0 else -np.inf)
        self.rms_db: float = rms_db if rms_db is not None else (20 * np.log10(rms_val) if rms_val > 0 else -np.inf)
        self.crest: float = self.peak_db - self.rms_db

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return {
            'peak': self.peak,
            'rms': self.rms,
            'peak_db': self.peak_db,
            'rms_db': self.rms_db,
            'crest': self.crest
        }


class MeasurementUtilities:
    """
    Shared measurement and logging utilities for audio processing.

    Consolidates boilerplate code used across adaptive_mode, continuous_mode, etc.
    """

    @staticmethod
    def measure_audio(audio: np.ndarray, label: str = "") -> AudioMeasurement:
        """
        Measure audio signal: peak, RMS, crest factor.

        Args:
            audio: Audio array to measure
            label: Optional label for debug output

        Returns:
            AudioMeasurement object with peak, RMS, crest factor
        """
        peak = np.max(np.abs(audio))
        rms_val = rms(audio)
        measurement = AudioMeasurement(peak, rms_val)

        if label:
            debug(f"[{label}] Peak: {measurement.peak_db:.2f} dB, "
                  f"RMS: {measurement.rms_db:.2f} dB, "
                  f"Crest: {measurement.crest:.2f} dB")

        return measurement

    @staticmethod
    def log_processing_step(step_name: str, before: AudioMeasurement,
                           after: AudioMeasurement,
                           additional_info: str = "") -> None:
        """
        Log before/after measurements for a processing step.

        Args:
            step_name: Name of processing step (e.g., "Compression", "Expansion")
            before: AudioMeasurement before processing
            after: AudioMeasurement after processing
            additional_info: Optional additional info to log
        """
        peak_delta = after.peak_db - before.peak_db
        rms_delta = after.rms_db - before.rms_db
        crest_delta = after.crest - before.crest

        debug(f"[{step_name}] Peak: {before.peak_db:.2f} → {after.peak_db:.2f} dB "
              f"(Δ {peak_delta:+.2f} dB)")
        debug(f"[{step_name}] RMS: {before.rms_db:.2f} → {after.rms_db:.2f} dB "
              f"(Δ {rms_delta:+.2f} dB)")
        debug(f"[{step_name}] Crest: {before.crest:.2f} → {after.crest:.2f} dB "
              f"(Δ {crest_delta:+.2f} dB)")

        if additional_info:
            debug(f"[{step_name}] {additional_info}")

    @staticmethod
    def crest_delta_info(before: AudioMeasurement, after: AudioMeasurement) -> str:
        """
        Get human-readable crest factor change info.

        Args:
            before: Measurement before processing
            after: Measurement after processing

        Returns:
            Formatted string describing the crest change
        """
        crest_delta = after.crest - before.crest
        return f"Crest {before.crest:.2f} → {after.crest:.2f} dB (Δ {crest_delta:+.2f} dB)"
