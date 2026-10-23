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

# The one table of values assumed for a dimension a fingerprint does not carry
# (a partial or old .25d cache, a failed analyzer). Raw `fp.get('<dim>', <n>)`
# fallbacks elsewhere re-typed these and had drifted apart (#5795): read them
# through FingerprintUnpacker, or fingerprint_default() where an unpacker is
# overkill. A site whose "default" is really a neutral element of its own
# computation (a band share that equals its ideal, a term in a sum) is not a
# fingerprint default and keeps its local value.
FINGERPRINT_DEFAULTS: dict[str, float] = {
    'lufs': -14.0,
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
    - Semantic access: unpacker.lufs instead of fp.get('lufs', -14.0)
    - Single source of truth for defaults
    - Lazy evaluation: Only extract what's needed
    - Better IDE autocomplete and type checking
    """

    _fp: dict[str, float]

    def _get(self, key: str) -> float:
        return self._fp.get(key, FINGERPRINT_DEFAULTS[key])

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

    @property
    def lufs(self) -> float:
        """Integrated loudness (LUFS). Default: -14.0"""
        return self._get('lufs')

    @property
    def crest_db(self) -> float:
        """Crest factor in dB (peak-to-RMS ratio). Default: 12.0"""
        return self._get('crest_db')

    @property
    def bass_mid_ratio(self) -> float:
        """Bass to mid-range energy ratio. Default: 0.0"""
        return self._get('bass_mid_ratio')

    # =========================================================================
    # Frequency (7D) - all bands
    # =========================================================================

    @property
    def sub_bass_pct(self) -> float:
        """Sub-bass energy percentage (< 60 Hz). Default: 0.05"""
        return self._get('sub_bass_pct')

    @property
    def bass_pct(self) -> float:
        """Bass energy percentage (60-200 Hz). Default: 0.15"""
        return self._get('bass_pct')

    @property
    def low_mid_pct(self) -> float:
        """Low-mid energy percentage (200-500 Hz). Default: 0.10"""
        return self._get('low_mid_pct')

    @property
    def mid_pct(self) -> float:
        """Mid energy percentage (500-2000 Hz). Default: 0.20"""
        return self._get('mid_pct')

    @property
    def upper_mid_pct(self) -> float:
        """Upper-mid energy percentage (2-4 kHz). Default: 0.25"""
        return self._get('upper_mid_pct')

    @property
    def presence_pct(self) -> float:
        """Presence energy percentage (4-8 kHz). Default: 0.15"""
        return self._get('presence_pct')

    @property
    def air_pct(self) -> float:
        """Air energy percentage (> 8 kHz). Default: 0.10"""
        return self._get('air_pct')

    # =========================================================================
    # Temporal (4D)
    # =========================================================================

    @property
    def tempo_bpm(self) -> float:
        """Estimated tempo in BPM. Default: 120.0"""
        return self._get('tempo_bpm')

    @property
    def rhythm_stability(self) -> float:
        """Rhythm stability metric 0.0-1.0. Default: 0.5"""
        return self._get('rhythm_stability')

    @property
    def transient_density(self) -> float:
        """Transient density metric 0.0-1.0. Default: 0.5"""
        return self._get('transient_density')

    @property
    def silence_ratio(self) -> float:
        """Silence ratio 0.0-1.0. Default: 0.0"""
        return self._get('silence_ratio')

    # =========================================================================
    # Spectral (3D) - brightness indicators
    # =========================================================================

    @property
    def spectral_centroid(self) -> float:
        """Spectral centroid (brightness) 0.0-1.0. Default: 0.5"""
        return self._get('spectral_centroid')

    @property
    def spectral_rolloff(self) -> float:
        """Spectral rolloff frequency 0.0-1.0. Default: 0.5"""
        return self._get('spectral_rolloff')

    @property
    def spectral_flatness(self) -> float:
        """Spectral flatness (noisiness) 0.0-1.0. Default: 0.5"""
        return self._get('spectral_flatness')

    # =========================================================================
    # Harmonic (3D)
    # =========================================================================

    @property
    def harmonic_ratio(self) -> float:
        """Harmonic content ratio 0.0-1.0. Default: 0.5"""
        return self._get('harmonic_ratio')

    @property
    def pitch_stability(self) -> float:
        """Pitch stability metric 0.0-1.0. Default: 0.5"""
        return self._get('pitch_stability')

    @property
    def chroma_energy(self) -> float:
        """Chroma energy distribution 0.0-1.0. Default: 0.5"""
        return self._get('chroma_energy')

    # =========================================================================
    # Variation (3D)
    # =========================================================================

    @property
    def dynamic_range_variation(self) -> float:
        """Dynamic range variation 0.0-1.0. Default: 0.5"""
        return self._get('dynamic_range_variation')

    @property
    def loudness_variation_std(self) -> float:
        """Loudness variation standard deviation. Default: 0.0"""
        return self._get('loudness_variation_std')

    @property
    def peak_consistency(self) -> float:
        """Peak consistency metric 0.0-1.0. Default: 0.5"""
        return self._get('peak_consistency')

    # =========================================================================
    # Stereo (2D)
    # =========================================================================

    @property
    def stereo_width(self) -> float:
        """Stereo width metric 0.0-1.0. Default: 0.5"""
        return self._get('stereo_width')

    @property
    def phase_correlation(self) -> float:
        """Phase correlation -1.0 to +1.0. Default: 1.0"""
        return self._get('phase_correlation')

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
