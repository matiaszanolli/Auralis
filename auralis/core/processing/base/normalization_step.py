# -*- coding: utf-8 -*-

"""
Normalization Step
~~~~~~~~~~~~~~~~~~

Represents a single gain adjustment step in the normalization pipeline.
Consolidates the measure-adjust-remeasure pattern.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Optional

import numpy as np

from ....dsp.basic import amplify, rms
from ....dsp.unified import calculate_loudness_units
from .db_conversion import DBConversion
from .processing_logger import ProcessingLogger


class NormalizationStep:
    """
    Represents a single gain adjustment step in the normalization pipeline.
    Consolidates the measure-adjust-remeasure pattern.
    """

    def __init__(self, step_name: str, stage_label: Optional[str] = None) -> None:
        """
        Initialize normalization step.

        Args:
            step_name: Name of the step (e.g., "RMS Boost", "LUFS Normalization")
            stage_label: Optional pre-logging label (e.g., "Pre-Final")
        """
        self.step_name: str = step_name
        self.stage_label: Optional[str] = stage_label
        self.before_measurement: Optional[Dict[str, float]] = None
        self.after_measurement: Optional[Dict[str, float]] = None
        self.gain_applied_db: float = 0.0

    def measure_before(self, audio: np.ndarray, use_lufs: bool = False,
                      sample_rate: Optional[int] = None) -> Dict[str, float]:
        """
        Measure audio before adjustment.

        Args:
            audio: Audio array
            use_lufs: Whether to include LUFS measurement
            sample_rate: Sample rate (required if use_lufs=True)

        Returns:
            Dictionary with measurements (peak_db, rms_db, crest, [lufs])
        """
        peak = np.max(np.abs(audio))
        peak_db = DBConversion.to_db(peak)
        rms_val = rms(audio)
        rms_db = DBConversion.to_db(rms_val)
        crest = peak_db - rms_db

        measurement = {
            'peak_db': peak_db,
            'rms_db': rms_db,
            'crest': crest,
            'peak': peak,
            'rms': rms_val
        }

        if use_lufs and sample_rate:
            lufs = calculate_loudness_units(audio, sample_rate)
            measurement['lufs'] = lufs

        self.before_measurement = measurement

        if self.stage_label:
            if 'lufs' in measurement:
                ProcessingLogger.pre_stage(self.stage_label, peak_db, measurement['lufs'])
            else:
                ProcessingLogger.pre_stage(self.stage_label, peak_db, rms_db, crest)

        return measurement

    def apply_gain(self, audio: np.ndarray, gain_db: float) -> np.ndarray:
        """
        Apply gain adjustment to audio.

        Args:
            audio: Input audio
            gain_db: Gain to apply in dB

        Returns:
            Audio with gain applied
        """
        if abs(gain_db) > 0.01:  # Only apply if meaningful change
            audio = amplify(audio, gain_db)
            self.gain_applied_db = gain_db

        return audio

    def measure_after(self, audio: np.ndarray, use_lufs: bool = False,
                     sample_rate: Optional[int] = None) -> Dict[str, float]:
        """
        Measure audio after adjustment.

        Args:
            audio: Audio array
            use_lufs: Whether to include LUFS measurement
            sample_rate: Sample rate (required if use_lufs=True)

        Returns:
            Dictionary with measurements
        """
        peak = np.max(np.abs(audio))
        peak_db = DBConversion.to_db(peak)
        rms_val = rms(audio)
        rms_db = DBConversion.to_db(rms_val)
        crest = peak_db - rms_db

        measurement: Dict[str, float] = {
            'peak_db': peak_db,
            'rms_db': rms_db,
            'crest': crest,
            'peak': peak,
            'rms': rms_val
        }

        if use_lufs and sample_rate:
            lufs = calculate_loudness_units(audio, sample_rate)
            measurement['lufs'] = lufs

        self.after_measurement = measurement
        return measurement

    def log_summary(self) -> None:
        """Log before/after summary for this step."""
        if self.before_measurement and self.after_measurement:
            if 'lufs' in self.before_measurement:
                # LUFS-based logging (continuous mode)
                lufs_delta = (self.after_measurement.get('lufs', 0) -
                            self.before_measurement.get('lufs', 0))
                peak_delta = (self.after_measurement['peak_db'] -
                            self.before_measurement['peak_db'])
                print(f"[{self.step_name}] LUFS: {self.before_measurement.get('lufs', 0):.1f} → "
                      f"{self.after_measurement.get('lufs', 0):.1f} (Δ {lufs_delta:+.1f}), "
                      f"Peak: {self.before_measurement['peak_db']:.2f} → "
                      f"{self.after_measurement['peak_db']:.2f} dB (Δ {peak_delta:+.2f})")
            else:
                # RMS/Crest-based logging (adaptive mode)
                peak_delta = (self.after_measurement['peak_db'] -
                            self.before_measurement['peak_db'])
                rms_delta = (self.after_measurement['rms_db'] -
                           self.before_measurement['rms_db'])
                crest_delta = (self.after_measurement['crest'] -
                             self.before_measurement['crest'])
                print(f"[{self.step_name}] Peak: {self.before_measurement['peak_db']:.2f} → "
                      f"{self.after_measurement['peak_db']:.2f} dB (Δ {peak_delta:+.2f}), "
                      f"RMS: {self.before_measurement['rms_db']:.2f} → "
                      f"{self.after_measurement['rms_db']:.2f} dB (Δ {rms_delta:+.2f})")
