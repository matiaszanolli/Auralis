"""
Full Audio Measurement
~~~~~~~~~~~~~~~~~~~~~~~

Complete audio measurement at any point in processing pipeline.
Consolidates all measurement types (peak, RMS, crest, LUFS) in one place.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from ....dsp.basic import rms
from ....dsp.unified import calculate_loudness_units
from .db_conversion import DBConversion


class FullAudioMeasurement:
    """
    Complete audio measurement at any point in processing pipeline.
    Consolidates all measurement types (peak, RMS, crest, LUFS) in one place.
    """

    def __init__(self, audio: np.ndarray, sample_rate: int | None = None, label: str | None = None) -> None:
        """
        Initialize with comprehensive audio analysis.

        Args:
            audio: Audio array to measure
            sample_rate: Sample rate (optional, for LUFS calculation)
            label: Optional label for identification
        """
        self.label: str | None = label
        self.peak: float = np.max(np.abs(audio))
        self.peak_db: float = DBConversion.to_db(self.peak)
        self.rms: float = rms(audio)
        self.rms_db: float = DBConversion.to_db(self.rms)
        self.crest: float = self.peak_db - self.rms_db
        self.lufs: float | None = None

        if sample_rate:
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
