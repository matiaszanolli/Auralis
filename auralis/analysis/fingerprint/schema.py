"""
Fingerprint Dimension Schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Single source of truth for what each of the 25 fingerprint dimensions means,
what unit it's stored in, and what its semantic range is.

Historical context: several downstream consumers were written assuming band
energy percentages were stored as 0–100 percentages and spectral_centroid in
Hz, but the actual fingerprint stores them as 0–1 fractions / 0–1 normalized
values. The bug collapsed the "continuous space" to a single point per source
because every deficit calculation hit the clip floor. This module centralizes
the conventions so consumers can't get them wrong again.

Use the constants and helpers here instead of hard-coding magic numbers.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

from enum import Enum


class Unit(str, Enum):
    """How a fingerprint dimension is encoded."""

    FRACTION = "fraction"          # 0.0 - 1.0
    NORMALIZED = "normalized"      # 0.0 - 1.0, scale defined per dimension
    DECIBELS = "dB"                # true dB value
    LUFS = "LUFS"                  # ITU-R BS.1770 loudness
    BPM = "BPM"


# Centroid is normalized so 1.0 corresponds to this frequency.
# Matches SpectralOperations.calculate_spectral_centroid (#3xxx) which uses
# MetricUtils.normalize_to_range(centroid_median, 8000.0, clip=True).
CENTROID_NORMALIZATION_HZ: float = 8000.0


# (unit, semantic_min, semantic_max) per dimension.
# semantic_min/max are typical, not absolute — used for normalization.
DIMENSION_SCHEMA: dict[str, tuple[Unit, float, float]] = {
    # 7-band spectral energy distribution (sums to ~1.0 across the bands)
    'sub_bass_pct':              (Unit.FRACTION,   0.00, 0.30),
    'bass_pct':                  (Unit.FRACTION,   0.05, 0.50),
    'low_mid_pct':               (Unit.FRACTION,   0.05, 0.40),
    'mid_pct':                   (Unit.FRACTION,   0.05, 0.50),
    'upper_mid_pct':             (Unit.FRACTION,   0.02, 0.30),
    'presence_pct':              (Unit.FRACTION,   0.00, 0.20),
    'air_pct':                   (Unit.FRACTION,   0.00, 0.25),

    # Loudness / dynamics
    'lufs':                      (Unit.LUFS,      -40.0,  -6.0),
    'crest_db':                  (Unit.DECIBELS,   5.0,  22.0),
    'bass_mid_ratio':            (Unit.DECIBELS, -10.0,  20.0),

    # Rhythm / temporal
    'tempo_bpm':                 (Unit.BPM,       40.0, 200.0),
    'rhythm_stability':          (Unit.NORMALIZED, 0.0, 1.0),
    'transient_density':         (Unit.NORMALIZED, 0.0, 1.0),
    'silence_ratio':             (Unit.NORMALIZED, 0.0, 1.0),

    # Spectral character (centroid/rolloff are normalized 0-1 where 1.0 = CENTROID_NORMALIZATION_HZ)
    'spectral_centroid':         (Unit.NORMALIZED, 0.0, 1.0),
    'spectral_rolloff':          (Unit.NORMALIZED, 0.0, 1.0),
    'spectral_flatness':         (Unit.NORMALIZED, 0.0, 1.0),

    # Tonal
    'harmonic_ratio':            (Unit.NORMALIZED, 0.0, 1.0),
    'pitch_stability':           (Unit.NORMALIZED, 0.0, 1.0),
    'chroma_energy':             (Unit.NORMALIZED, 0.0, 1.0),

    # Variation / consistency
    'dynamic_range_variation':   (Unit.NORMALIZED, 0.0, 1.0),
    'loudness_variation_std':    (Unit.DECIBELS,   0.0, 10.0),
    'peak_consistency':          (Unit.NORMALIZED, 0.0, 1.0),

    # Stereo
    'stereo_width':              (Unit.NORMALIZED, 0.0, 1.0),
    'phase_correlation':         (Unit.NORMALIZED, 0.0, 1.0),
}


# Bands of the 7-band fingerprint energy split, in Hz. Useful for EQ targeting.
BAND_RANGES_HZ: dict[str, tuple[float, float]] = {
    'sub_bass_pct': (20.0,    60.0),
    'bass_pct':     (60.0,   250.0),
    'low_mid_pct':  (250.0,  500.0),
    'mid_pct':      (500.0,  2000.0),
    'upper_mid_pct':(2000.0, 4000.0),
    'presence_pct': (4000.0, 6000.0),
    'air_pct':      (6000.0, 20000.0),
}


def centroid_to_hz(centroid_normalized: float) -> float:
    """Convert a normalized centroid value back to Hz.

    The fingerprint stores spectral_centroid clipped to [0, 1] where 1.0
    corresponds to CENTROID_NORMALIZATION_HZ (8 kHz). Use this anywhere a
    consumer needs to reason about brightness in Hz units.
    """
    return float(centroid_normalized) * CENTROID_NORMALIZATION_HZ


def rolloff_to_hz(rolloff_normalized: float) -> float:
    """Convert a normalized 85%-rolloff value back to Hz."""
    return float(rolloff_normalized) * CENTROID_NORMALIZATION_HZ


__all__ = [
    "Unit",
    "CENTROID_NORMALIZATION_HZ",
    "DIMENSION_SCHEMA",
    "BAND_RANGES_HZ",
    "centroid_to_hz",
    "rolloff_to_hz",
]
