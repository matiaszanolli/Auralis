"""
Fingerprint Unpacker
~~~~~~~~~~~~~~~~~~~~

Type-safe unpacker for 25D fingerprint dictionary.

Provides semantic property access instead of repeated fp.get() calls,
with centralized defaults and lazy evaluation.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import dataclass
from typing import Any

from ...dsp.utils.loudness_targets import DEFAULT_TARGET_LUFS

# The one table of values assumed for a dimension a fingerprint does not carry
# (a partial or old .25d cache, a failed analyzer). Raw `fp.get('<dim>', <n>)`
# fallbacks elsewhere re-typed these and had drifted apart (#5795): read them
# through FingerprintUnpacker, or fingerprint_default() where an unpacker is
# overkill. A site whose "default" is really a neutral element of its own
# computation (a band share that equals its ideal, a term in a sum) is not a
# fingerprint default and keeps its local value.
FINGERPRINT_DEFAULTS: dict[str, float] = {
    # A track with no measured loudness is assumed to sit at the default
    # target (#6226) — the value downstream target-derivation expects.
    'lufs': DEFAULT_TARGET_LUFS,
    'crest_db': 12.0,
    'bass_mid_ratio': 0.0,
    'sub_bass_pct': 0.05,
    'bass_pct': 0.15,
    'low_mid_pct': 0.10,
    'mid_pct': 0.20,
    'upper_mid_pct': 0.25,
    'presence_pct': 0.15,
    'air_pct': 0.10,
    'tempo_bpm': 120.0,
    'rhythm_stability': 0.5,
    'transient_density': 0.5,
    'silence_ratio': 0.0,
    'spectral_centroid': 0.5,
    'spectral_rolloff': 0.5,
    'spectral_flatness': 0.5,
    'harmonic_ratio': 0.5,
    'pitch_stability': 0.5,
    'chroma_energy': 0.5,
    'dynamic_range_variation': 0.5,
    'loudness_variation_std': 0.0,
    'peak_consistency': 0.5,
    'stereo_width': 0.5,
    'phase_correlation': 1.0,
}


# The 25 dimension accessors are generated from this table by
# FingerprintUnpacker.__getattr__ (#6272) — one definition instead of 25
# hand-written property blocks, and a new dimension means adding one entry.
_DIMENSION_KEYS: dict[str, str] = {}





@dataclass
class FingerprintUnpacker:
    """
    Type-safe unpacker for 25D fingerprint dictionary.

    Provides semantic property access instead of repeated fp.get() calls.
    Lazy extraction: only retrieves values when accessed.

    Fingerprint structure:
    - Dynamics (3D): LUFS, crest factor, bass/mid ratio
    - Frequency (7D): Energy distribution across 7 bands
    - Temporal (4D): Tempo, rhythm, transients, silence
    - Spectral (3D): Centroid, rolloff, flatness
    - Harmonic (3D): Harmonic ratio, pitch stability, chroma
    - Variation (3D): Dynamic range variation, loudness variation, peak consistency
    - Stereo (2D): Stereo width, phase correlation

    Total: 25 dimensions

    Usage:
        >>> unpacker = FingerprintUnpacker.from_dict(fp)
        >>> print(unpacker.lufs)  # Access via property
        -14.5
        >>> print(unpacker.bass_pct)
        0.23

    Benefits:
    - Type safety: Properties return typed values
    - Semantic access: unpacker.lufs instead of fp.get('lufs', <literal>)
    - Single source of truth for defaults
    - Lazy evaluation: Only extract what's needed
    - Better IDE autocomplete and type checking
    """

    _fp: dict[str, float]

    def _get(self, key: str) -> float:
        return self._fp.get(key, FINGERPRINT_DEFAULTS[key])

    def __getattr__(self, name: str) -> float:
        key = _DIMENSION_KEYS.get(name)
        if key is None:
            raise AttributeError(name)
        return self._get(key)


    def as_dict(self) -> dict[str, float]:
        """Return the complete defaulted 25D numeric fingerprint."""
        return {
            'lufs': self.lufs,
            'crest_db': self.crest_db,
            'bass_mid_ratio': self.bass_mid_ratio,
            'sub_bass_pct': self.sub_bass_pct,
            'bass_pct': self.bass_pct,
            'low_mid_pct': self.low_mid_pct,
            'mid_pct': self.mid_pct,
            'upper_mid_pct': self.upper_mid_pct,
            'presence_pct': self.presence_pct,
            'air_pct': self.air_pct,
            'tempo_bpm': self.tempo_bpm,
            'rhythm_stability': self.rhythm_stability,
            'transient_density': self.transient_density,
            'silence_ratio': self.silence_ratio,
            'spectral_centroid': self.spectral_centroid,
            'spectral_rolloff': self.spectral_rolloff,
            'spectral_flatness': self.spectral_flatness,
            'harmonic_ratio': self.harmonic_ratio,
            'pitch_stability': self.pitch_stability,
            'chroma_energy': self.chroma_energy,
            'dynamic_range_variation': self.dynamic_range_variation,
            'loudness_variation_std': self.loudness_variation_std,
            'peak_consistency': self.peak_consistency,
            'stereo_width': self.stereo_width,
            'phase_correlation': self.phase_correlation,
        }

    # =========================================================================
    # Dynamics (3D)
    # =========================================================================

    # =========================================================================
    # Frequency (7D) - all bands
    # =========================================================================

    # =========================================================================
    # Temporal (4D)
    # =========================================================================

    # =========================================================================
    # Spectral (3D) - brightness indicators
    # =========================================================================

    # =========================================================================
    # Harmonic (3D)
    # =========================================================================

    # =========================================================================
    # Variation (3D)
    # =========================================================================

    # =========================================================================
    # Stereo (2D)
    # =========================================================================

    # =========================================================================
    # Factory Method
    # =========================================================================

    @classmethod
    def from_dict(cls, fp: dict[str, float]) -> FingerprintUnpacker:
        """
        Create unpacker from raw fingerprint dict.

        Args:
            fp: Fingerprint dictionary with up to 25 dimensions

        Returns:
            FingerprintUnpacker instance

        Example:
            >>> fp = {'lufs': -12.5, 'crest_db': 10.0, 'bass_pct': 0.20}
            >>> unpacker = FingerprintUnpacker.from_dict(fp)
            >>> print(unpacker.lufs)
            -12.5
            >>> print(unpacker.bass_pct)
            0.20
            >>> print(unpacker.air_pct)  # Not in dict, uses default
            0.10
        """
        return cls(_fp=fp)


def fingerprint_default(dimension: str) -> float:
    """The assumed value of ``dimension`` when a fingerprint does not carry it."""
    return FINGERPRINT_DEFAULTS[dimension]


_DIMENSION_KEYS.update({
    'lufs': 'lufs',
    'crest_db': 'crest_db',
    'bass_mid_ratio': 'bass_mid_ratio',
    'sub_bass_pct': 'sub_bass_pct',
    'bass_pct': 'bass_pct',
    'low_mid_pct': 'low_mid_pct',
    'mid_pct': 'mid_pct',
    'upper_mid_pct': 'upper_mid_pct',
    'presence_pct': 'presence_pct',
    'air_pct': 'air_pct',
    'tempo_bpm': 'tempo_bpm',
    'rhythm_stability': 'rhythm_stability',
    'transient_density': 'transient_density',
    'silence_ratio': 'silence_ratio',
    'spectral_centroid': 'spectral_centroid',
    'spectral_rolloff': 'spectral_rolloff',
    'spectral_flatness': 'spectral_flatness',
    'harmonic_ratio': 'harmonic_ratio',
    'pitch_stability': 'pitch_stability',
    'chroma_energy': 'chroma_energy',
    'dynamic_range_variation': 'dynamic_range_variation',
    'loudness_variation_std': 'loudness_variation_std',
    'peak_consistency': 'peak_consistency',
    'stereo_width': 'stereo_width',
    'phase_correlation': 'phase_correlation',
})
