"""
Fingerprint Unpacker
~~~~~~~~~~~~~~~~~~~~

Type-safe unpacker for 25D fingerprint dictionary.

Provides semantic property access instead of repeated fp.get() calls,
with centralized defaults and lazy evaluation.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass


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

    _fp: dict

    # =========================================================================
    # Dynamics (3D)
    # =========================================================================

    @property
    def lufs(self) -> float:
        """Integrated loudness (LUFS). Default: -14.0"""
        return self._fp.get('lufs', -14.0)

    @property
    def crest_db(self) -> float:
        """Crest factor in dB (peak-to-RMS ratio). Default: 12.0"""
        return self._fp.get('crest_db', 12.0)

    @property
    def bass_mid_ratio(self) -> float:
        """Bass to mid-range energy ratio. Default: 0.0"""
        return self._fp.get('bass_mid_ratio', 0.0)

    # =========================================================================
    # Frequency (7D) - all bands
    # =========================================================================

    @property
    def sub_bass_pct(self) -> float:
        """Sub-bass energy percentage (< 60 Hz). Default: 0.05"""
        return self._fp.get('sub_bass_pct', 0.05)

    @property
    def bass_pct(self) -> float:
        """Bass energy percentage (60-200 Hz). Default: 0.15"""
        return self._fp.get('bass_pct', 0.15)

    @property
    def low_mid_pct(self) -> float:
        """Low-mid energy percentage (200-500 Hz). Default: 0.10"""
        return self._fp.get('low_mid_pct', 0.10)

    @property
    def mid_pct(self) -> float:
        """Mid energy percentage (500-2000 Hz). Default: 0.20"""
        return self._fp.get('mid_pct', 0.20)

    @property
    def upper_mid_pct(self) -> float:
        """Upper-mid energy percentage (2-4 kHz). Default: 0.25"""
        return self._fp.get('upper_mid_pct', 0.25)

    @property
    def presence_pct(self) -> float:
        """Presence energy percentage (4-8 kHz). Default: 0.15"""
        return self._fp.get('presence_pct', 0.15)

    @property
    def air_pct(self) -> float:
        """Air energy percentage (> 8 kHz). Default: 0.10"""
        return self._fp.get('air_pct', 0.10)

    # =========================================================================
    # Temporal (4D)
    # =========================================================================

    @property
    def tempo_bpm(self) -> float:
        """Estimated tempo in BPM. Default: 120.0"""
        return self._fp.get('tempo_bpm', 120.0)

    @property
    def rhythm_stability(self) -> float:
        """Rhythm stability metric 0.0-1.0. Default: 0.5"""
        return self._fp.get('rhythm_stability', 0.5)

    @property
    def transient_density(self) -> float:
        """Transient density metric 0.0-1.0. Default: 0.5"""
        return self._fp.get('transient_density', 0.5)

    @property
    def silence_ratio(self) -> float:
        """Silence ratio 0.0-1.0. Default: 0.0"""
        return self._fp.get('silence_ratio', 0.0)

    # =========================================================================
    # Spectral (3D) - brightness indicators
    # =========================================================================

    @property
    def spectral_centroid(self) -> float:
        """Spectral centroid (brightness) 0.0-1.0. Default: 0.5"""
        return self._fp.get('spectral_centroid', 0.5)

    @property
    def spectral_rolloff(self) -> float:
        """Spectral rolloff frequency 0.0-1.0. Default: 0.5"""
        return self._fp.get('spectral_rolloff', 0.5)

    @property
    def spectral_flatness(self) -> float:
        """Spectral flatness (noisiness) 0.0-1.0. Default: 0.5"""
        return self._fp.get('spectral_flatness', 0.5)

    # =========================================================================
    # Harmonic (3D)
    # =========================================================================

    @property
    def harmonic_ratio(self) -> float:
        """Harmonic content ratio 0.0-1.0. Default: 0.5"""
        return self._fp.get('harmonic_ratio', 0.5)

    @property
    def pitch_stability(self) -> float:
        """Pitch stability metric 0.0-1.0. Default: 0.5"""
        return self._fp.get('pitch_stability', 0.5)

    @property
    def chroma_energy(self) -> float:
        """Chroma energy distribution 0.0-1.0. Default: 0.5"""
        return self._fp.get('chroma_energy', 0.5)

    # =========================================================================
    # Variation (3D)
    # =========================================================================

    @property
    def dynamic_range_variation(self) -> float:
        """Dynamic range variation 0.0-1.0. Default: 0.5"""
        return self._fp.get('dynamic_range_variation', 0.5)

    @property
    def loudness_variation_std(self) -> float:
        """Loudness variation standard deviation. Default: 0.0"""
        return self._fp.get('loudness_variation_std', 0.0)

    @property
    def peak_consistency(self) -> float:
        """Peak consistency metric 0.0-1.0. Default: 0.5"""
        return self._fp.get('peak_consistency', 0.5)

    # =========================================================================
    # Stereo (2D)
    # =========================================================================

    @property
    def stereo_width(self) -> float:
        """Stereo width metric 0.0-1.0. Default: 0.5"""
        return self._fp.get('stereo_width', 0.5)

    @property
    def phase_correlation(self) -> float:
        """Phase correlation -1.0 to +1.0. Default: 1.0"""
        return self._fp.get('phase_correlation', 1.0)

    # =========================================================================
    # Factory Method
    # =========================================================================

    @classmethod
    def from_dict(cls, fp: dict) -> 'FingerprintUnpacker':
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
