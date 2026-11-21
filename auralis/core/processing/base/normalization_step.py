"""
Normalization Step
~~~~~~~~~~~~~~~~~~

Represents a single gain adjustment step in the normalization pipeline.
Consolidates the measure-adjust-remeasure pattern.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


import numpy as np

from ....dsp.basic import amplify
from ....dsp.utils.conversion import level_stats
from ....dsp.utils.adaptive import calculate_loudness_units
from .processing_logger import ProcessingLogger


class NormalizationStep:
    """
    Represents a single gain adjustment step in the normalization pipeline.
    Consolidates the measure-adjust-remeasure pattern.
    """

    def __init__(self, step_name: str, stage_label: str | None = None) -> None:
        """
        Initialize normalization step.

        Args:
            step_name: Name of the step (e.g., "RMS Boost", "LUFS Normalization")
            stage_label: Optional pre-logging label (e.g., "Pre-Final")
        """
        self.step_name: str = step_name
        self.stage_label: str | None = stage_label
        self.before_measurement: dict[str, float] | None = None
        self.after_measurement: dict[str, float] | None = None
        self.gain_applied_db: float = 0.0

    def measure_before(self, audio: np.ndarray, use_lufs: bool = False,
                      sample_rate: int | None = None) -> dict[str, float]:
        """
        Measure audio before adjustment.

        Args:
            audio: Audio array
            use_lufs: Whether to include LUFS measurement
            sample_rate: Sample rate (required if use_lufs=True)

        Returns:
            Dictionary with measurements (peak_db, rms_db, crest, [lufs])
        """
        measurement = self._measure(audio, use_lufs, sample_rate)
        self.before_measurement = measurement

        if self.stage_label:
            if 'lufs' in measurement:
                ProcessingLogger.pre_stage(self.stage_label, measurement['peak_db'], measurement['lufs'])
            else:
                ProcessingLogger.pre_stage(
                    self.stage_label, measurement['peak_db'], measurement['rms_db'], measurement['crest']
                )

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
                     sample_rate: int | None = None) -> dict[str, float]:
        """
        Measure audio after adjustment.

        Args:
            audio: Audio array
            use_lufs: Whether to include LUFS measurement
            sample_rate: Sample rate (required if use_lufs=True)

        Returns:
            Dictionary with measurements
        """
        measurement = self._measure(audio, use_lufs, sample_rate)
        self.after_measurement = measurement
        return measurement

    @staticmethod
    def _measure(audio: np.ndarray, use_lufs: bool, sample_rate: int | None) -> dict[str, float]:
        """peak/rms (linear and dB), crest (0.0 for silence, #6597) and optionally LUFS."""
        stats = level_stats(audio)
        measurement: dict[str, float] = {
            'peak_db': stats.peak_db,
            'rms_db': stats.rms_db,
            'crest': stats.crest_db,
            'peak': stats.peak,
            'rms': stats.rms,
        }
        if use_lufs and sample_rate:
            measurement['lufs'] = calculate_loudness_units(audio, sample_rate)
        return measurement
