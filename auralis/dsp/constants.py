"""
Shared DSP constants
~~~~~~~~~~~~~~~~~~~~

Single owner for numeric conventions used across dsp, analysis, and the
core config. Import this instead of retyping the literal (#6229).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

# Canonical processing FFT size. The live value is `UnifiedConfig.fft_size`
# (its default reads this constant); the settings classes below the config
# (EQSettings, SpectrumSettings, SpectrumOperations) default to the same
# constant so a bare construction can never silently disagree with the
# configured pipeline. The genre classifier's FeatureExtractor keeps its
# own separate contract constants (see auralis/analysis/ml).
DEFAULT_FFT_SIZE: int = 4096

#: The sample rate assumed when nothing else is known (#6636): constructor and
#: config defaults, nominal sizing, and the fallback for a processor with no
#: metadata. ``UnifiedConfig.internal_sample_rate`` defaults to it.
#: Mirrored by the frontend's DEFAULT_STREAM_SAMPLE_RATE (audioConstants.ts) and
#: the literal UserSettings.sample_rate column default (the library model layer
#: takes no dsp import); tests/regression/test_default_sample_rate_6636.py holds
#: them equal.
DEFAULT_SAMPLE_RATE: int = 44100

#: Median share of total spectral energy per fingerprint band, from the
#: deterministic 512-track corpus sample (July 2026) — the same calibration
#: ``auralis/core/processing/parameter_generator_eq.py``'s signed band gains
#: center on when no reference cloud supplies its own centers. ONE table for every
#: render path (``auralis/core/processing/mastering_targets.py``), so they cannot
#: drift again (#5695) — the hand-set "ideal shares" the fixed-target path used before tilted
#: every track by a content-independent bass-cut/treble-boost (bass clamped
#: at -6 dB, +9.5 dB summed high shelf on a corpus-median track).
#:
#: Derivations: ``presence`` is the corpus's combined upper-mid+presence
#: center (0.1030) minus the upper-mid center; ``sub_bass`` is the residual
#: that keeps the seven centers tiling to 1.0 (the band fractions the
#: fingerprint enforces sum to ~1, and the EQ law pins no sub-bass center
#: of its own — its low shelf keys on ``bass`` alone).
CORPUS_BAND_CENTERS: dict[str, float] = {
    'sub_bass': 0.1354,
    'bass': 0.4561,
    'low_mid': 0.1009,
    'mid': 0.1983,
    'upper_mid': 0.0733,
    'presence': 0.0297,
    'air': 0.0063,
}

#: Default spectral centroid in hertz for consumers that adapt EQ curves from
#: a raw centroid (#6219). The fingerprint table's normalised 'spectral_centroid'
#: (0.5) and this value describe the same default centre through two unit
#: conventions; FINGERPRINT_DEFAULTS['spectral_centroid_hz'] aliases this so
#: neither is retyped at call sites (and dsp/ never imports core/ for it).
SPECTRAL_CENTROID_HZ_DEFAULT: float = 2000.0
