"""
Full Audio Measurement
~~~~~~~~~~~~~~~~~~~~~~~

Complete audio measurement at any point in processing pipeline.
Consolidates all measurement types (peak, RMS, crest, LUFS) in one place.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


import numpy as np

from ....dsp.utils.adaptive import calculate_loudness_units
from ....dsp.utils.conversion import level_stats


class FullAudioMeasurement:
    """
    Complete audio measurement at any point in processing pipeline.
    Consolidates all measurement types (peak, RMS, crest, LUFS) in one place.
    """

    def __init__(
        self, audio: np.ndarray, sample_rate: int | None = None, label: str | None = None,
        lufs: float | None = None,
    ) -> None:
        """
        Initialize with comprehensive audio analysis.

        Args:
            audio: Audio array to measure
            sample_rate: Sample rate (optional, for LUFS calculation)
            label: Optional label for identification
            lufs: ``calculate_loudness_units(audio, sample_rate)`` when the caller
                already measured it; skips the K-weighting pass
        """
        self.label: str | None = label
        stats = level_stats(audio)  # crest 0.0 for silence, not NaN (#6597)
        self.peak: float = stats.peak
        self.peak_db: float = stats.peak_db
        self.rms: float = stats.rms
        self.rms_db: float = stats.rms_db
        self.crest: float = stats.crest_db
        self.lufs: float | None = lufs

        if lufs is None and sample_rate:
            self.lufs = calculate_loudness_units(audio, sample_rate)

    def to_dict(self) -> dict[str, float]:
        """Convert measurement to dictionary."""
        data: dict[str, float] = {
            'peak': self.peak,
            'peak_db': self.peak_db,
            'rms': self.rms,
            'rms_db': self.rms_db,
            'crest': self.crest
        }
        if self.lufs is not None:
            data['lufs'] = self.lufs
        return data

    def __str__(self) -> str:
        """String representation of measurement."""
        if self.lufs is not None:
            return (f"[{self.label or 'Measurement'}] Peak: {self.peak_db:.2f} dB, "
                   f"RMS: {self.rms_db:.2f} dB, Crest: {self.crest:.2f} dB, LUFS: {self.lufs:.1f}")
        else:
            return (f"[{self.label or 'Measurement'}] Peak: {self.peak_db:.2f} dB, "
                   f"RMS: {self.rms_db:.2f} dB, Crest: {self.crest:.2f} dB")
