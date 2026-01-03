# -*- coding: utf-8 -*-

"""
Fingerprint Parameter Mapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Converts 25D audio fingerprints into mastering parameters (EQ, dynamics, levels).

Maps fingerprint dimensions to processor configuration:
- Frequency distribution (7D) → 31-band EQ gains
- Dynamics (3D) → Compressor threshold, ratio, attack, release
- Temporal (4D) → Gate threshold, multiband settings
- Spectral (3D) → Presence, brightness controls
- Harmonic (3D) → Harmonic enhancement, saturation
- Variation (3D) → Dynamic range compression
- Stereo (2D) → Stereo width, phase correction

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, Dict, Optional

import numpy as np

from ...utils.logging import debug, info
from .metrics import BandNormalizationTable


class EQParameterMapper:
    """Maps frequency fingerprint dimensions to 31-band EQ gains"""

    def __init__(self) -> None:
        """Initialize EQ mapper with standard 31-band frequencies and normalization table"""
        # ISO 31-band EQ center frequencies (Hz)
        self.eq_bands = [
            20, 25, 31, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500,
            630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000,
            10000, 12500, 16000, 20000
        ]
        # Initialize band normalization table for vectorized band gain application
        self.band_table = BandNormalizationTable()

    def map_frequency_to_eq(self, fingerprint: Dict[str, Any]) -> Dict[int, float]:
        """
        Map 7D frequency distribution to 31-band EQ gains

        Uses vectorized BandNormalizationTable instead of 7 repetitive loops.
        Previously: 7 separate loops with hardcoded band ranges
        Now: Data-driven parameterized approach with single apply call

        Fingerprint dimensions used:
        - sub_bass_pct (20-60 Hz)
        - bass_pct (60-250 Hz)
        - low_mid_pct (250-500 Hz)
        - mid_pct (500-2k Hz)
        - upper_mid_pct (2k-4k Hz)
        - presence_pct (4k-6k Hz)
        - air_pct (6k-20k Hz)

        Returns:
            Dictionary mapping band index to gain in dB
        """
        return self.band_table.apply_to_fingerprint(fingerprint, self._normalize_to_db)

    def map_spectral_to_eq(self, fingerprint: Dict[str, Any]) -> Dict[int, float]:
        """
        Map spectral dimensions to targeted EQ adjustments

        Uses spectral centroid and flatness to enhance or smooth tonal character

        Fingerprint dimensions:
        - spectral_centroid: Brightness (Hz)
        - spectral_rolloff: High-frequency energy
        - spectral_flatness: Tonality vs noise
        """
        spectral_gains = {}

        centroid = fingerprint.get('spectral_centroid', 2000.0)
        rolloff = fingerprint.get('spectral_rolloff', 8000.0)
        flatness = fingerprint.get('spectral_flatness', 0.5)

        # Bright sounds (high centroid) - reduce upper mids slightly
        if centroid > 3000:
            spectral_gains.update({i: -2.0 for i in range(20, 24)})  # Upper mids

        # Dull sounds (low centroid) - enhance presence
        if centroid < 1500:
            spectral_gains.update({i: 3.0 for i in range(24, 26)})  # Presence bands

        # Very bright (high rolloff) - control air band
        if rolloff > 10000:
            spectral_gains.update({i: -3.0 for i in range(28, 31)})  # Air band

        # Very dull (low rolloff) - boost air band
        if rolloff < 5000:
            spectral_gains.update({i: 4.0 for i in range(28, 31)})  # Air band

        # Noise-like (high flatness) - reduce narrow peaks
        if flatness > 0.6:
            spectral_gains.update({i: -1.5 for i in [17, 20, 24]})  # Common resonance points

        return spectral_gains

    def _normalize_to_db(self, value: float, min_db: float, max_db: float) -> float:
        """Normalize a 0-1 value to dB range"""
        # Clamp value to 0-1
        value = np.clip(value, 0.0, 1.0)
        # Linear interpolation in dB range
        return min_db + (value * (max_db - min_db))

    def _apply_gain_saturation(self, gains: Dict[int, float], nominal_max: float = 12.0,
                               hard_max: float = 18.0) -> Dict[int, float]:
        """
        Apply non-linear saturation to EQ gains to prevent extreme values.

        Uses a saturation curve:
        - Below nominal_max: Linear (no change)
        - nominal_max to hard_max: Non-linear compression
        - Above hard_max: Hard clip

        Args:
            gains: Dictionary of band index to gain in dB
            nominal_max: Nominal maximum gain (dB) - typical operating range
            hard_max: Hard maximum gain (dB) - absolute limit before clipping

        Returns:
            Dictionary with saturated gains
        """
        saturated = {}
        for band_idx, gain in gains.items():
            # Apply saturation symmetrically for positive and negative gains
            abs_gain = abs(gain)
            sign = 1 if gain >= 0 else -1

            if abs_gain <= nominal_max:
                # Linear region - no change
                saturated[band_idx] = gain
            elif abs_gain <= hard_max:
                # Saturation region - non-linear compression
                # Compress the excess range (nominal_max to hard_max) to 50% width
                excess = abs_gain - nominal_max
                max_excess = hard_max - nominal_max
                # Saturation curve: soft knee that approaches hard_max asymptotically
                compressed_excess = max_excess * (1.0 - np.exp(-excess / max_excess))
                saturated_gain = nominal_max + compressed_excess
                saturated[band_idx] = sign * saturated_gain
            else:
                # Hard clip above hard_max
                saturated[band_idx] = sign * hard_max

        return saturated


class DynamicsParameterMapper:
    """Maps dynamics fingerprint dimensions to compressor/limiter settings"""

    def map_to_compressor(self, fingerprint: Dict[str, Any]) -> Dict[str, float]:
        """
        Map dynamics dimensions to compressor settings

        Fingerprint dimensions:
        - lufs: Integrated loudness (target level)
        - crest_db: Crest factor (dynamic range indicator)
        - bass_mid_ratio: Balance of low-end energy

        Returns:
            Dictionary with compressor parameters:
            - threshold: dB (where compression starts)
            - ratio: Compression ratio (1:1 to 8:1)
            - attack_ms: Attack time in milliseconds
            - release_ms: Release time in milliseconds
            - makeup_gain: dB of makeup gain
        """
        lufs = fingerprint.get('lufs', -16.0)
        crest = fingerprint.get('crest_db', 8.0)
        bass_mid_ratio = fingerprint.get('bass_mid_ratio', 1.0)

        # Crest factor indicates dynamic range
        # High crest = high dynamic range = need more compression
        ratio = self._calculate_compression_ratio(crest)

        # Threshold depends on how much control we need
        # Higher crest → lower threshold (catch more dynamics)
        threshold = self._calculate_threshold(crest, lufs)

        # Attack time depends on content type
        # Punchy content (high crest) needs faster attack
        attack = self._calculate_attack(crest)

        # Release depends on bass content
        # More bass → slower release (avoid pumping)
        release = self._calculate_release(bass_mid_ratio)

        # Makeup gain: bring peaks back up after compression
        makeup_gain = crest / 2.0  # Rough estimate

        return {
            'threshold': threshold,
            'ratio': ratio,
            'attack_ms': attack,
            'release_ms': release,
            'makeup_gain': makeup_gain
        }

    def map_to_multiband(self, fingerprint: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """
        Map dynamics to multiband compression settings

        Uses frequency distribution and variation to apply compression
        where it's most needed

        Returns:
            Dictionary with 3-band compressor settings:
            - low (0-250 Hz)
            - mid (250-2k Hz)
            - high (2k-20k Hz)
        """
        bass_pct = fingerprint.get('bass_pct', 0.2)
        mid_pct = fingerprint.get('mid_pct', 0.2)
        variation = fingerprint.get('dynamic_range_variation', 2.0)

        multiband = {}

        # Low band (bass) - heavier compression if bass-heavy
        multiband['low'] = {
            'threshold': -20 + (bass_pct * 10),
            'ratio': 2.0 + (bass_pct * 2),  # More compression for bass-heavy
            'attack_ms': 50,
            'release_ms': 300
        }

        # Mid band - standard compression
        multiband['mid'] = {
            'threshold': -18,
            'ratio': 2.0 + (variation * 0.5),
            'attack_ms': 30,
            'release_ms': 150
        }

        # High band - lighter compression
        multiband['high'] = {
            'threshold': -15,
            'ratio': 1.5 + (variation * 0.3),
            'attack_ms': 20,
            'release_ms': 100
        }

        return multiband

    def _calculate_compression_ratio(self, crest_db: float) -> float:
        """Calculate compression ratio based on crest factor"""
        # Low crest (< 6dB) = gentle compression (2:1)
        # Medium crest (6-10dB) = moderate compression (4:1)
        # High crest (> 10dB) = aggressive compression (6:1)
        if crest_db < 6:
            return 2.0
        elif crest_db < 10:
            return 2.0 + ((crest_db - 6) / 4) * 2  # 2:1 to 4:1
        else:
            return 4.0 + ((crest_db - 10) / 10) * 2  # 4:1 to 6:1

    def _calculate_threshold(self, crest_db: float, lufs: float) -> float:
        """Calculate compressor threshold"""
        # Threshold = LUFS + (crest / 2)
        # Higher crest → lower threshold (catch more dynamics)
        return lufs + (crest_db / 2.0)

    def _calculate_attack(self, crest_db: float) -> float:
        """Calculate attack time in milliseconds"""
        # Fast attack for punchy content (high crest)
        # Slow attack for smooth content (low crest)
        return max(5.0, 50.0 - (crest_db * 2.0))

    def _calculate_release(self, bass_mid_ratio: float) -> float:
        """Calculate release time in milliseconds"""
        # More bass → slower release (avoid pumping at low frequencies)
        return 100.0 + (bass_mid_ratio * 100.0)


class LevelParameterMapper:
    """Maps loudness dimensions to level matching settings"""

    def map_to_level_matching(self, fingerprint: Dict[str, Any], target_lufs: Optional[float] = None) -> Dict[str, float]:
        """
        Map loudness dimensions to level matching parameters

        Fingerprint dimensions:
        - lufs: Integrated loudness
        - loudness_variation_std: Loudness stability

        Returns:
            Dictionary with level matching settings:
            - target_lufs: Target loudness level
            - gain: Gain adjustment in dB
            - headroom: Safety headroom in dB
        """
        lufs = fingerprint.get('lufs', -16.0)
        loudness_var = fingerprint.get('loudness_variation_std', 1.0)

        # Use provided target or default based on content
        if target_lufs is None:
            target_lufs = -16.0  # Standard streaming loudness

        # Calculate gain adjustment
        gain = target_lufs - lufs

        # Headroom based on peak level and variation
        # More variation = more headroom needed
        peak_level = fingerprint.get('crest_db', 8.0)
        headroom = peak_level / 2.0 + loudness_var

        return {
            'target_lufs': target_lufs,
            'gain': gain,
            'headroom': headroom,
            'safety_margin': 1.0  # 1dB safety margin
        }


class HarmonicParameterMapper:
    """Maps harmonic dimensions to harmonic enhancement and saturation"""

    def map_to_harmonic_enhancement(self, fingerprint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map harmonic dimensions to enhancement settings

        Fingerprint dimensions:
        - harmonic_ratio: Harmonic vs percussive energy
        - pitch_stability: Pitch consistency
        - chroma_energy: Harmonic content strength

        Returns:
            Dictionary with harmonic enhancement settings
        """
        harmonic_ratio = fingerprint.get('harmonic_ratio', 0.5)
        pitch_stability = fingerprint.get('pitch_stability', 0.7)
        chroma_energy = fingerprint.get('chroma_energy', 0.5)

        # Enhance harmonic content if stable and strong
        saturation_amount = 0.0
        if harmonic_ratio > 0.7 and pitch_stability > 0.8:
            saturation_amount = min(0.3, chroma_energy / 2.0)

        # Harmonic exciters for weak harmonic content
        exciter_amount = 0.0
        if harmonic_ratio < 0.4:
            exciter_amount = (0.5 - harmonic_ratio) * 0.5

        return {
            'saturation': saturation_amount,
            'exciter': exciter_amount,
            'pitch_stability_score': pitch_stability,
            'harmonic_enhancement_enabled': harmonic_ratio > 0.5
        }


class ParameterMapper:
    """Main parameter mapper: orchestrates all mapping operations"""

    def __init__(self) -> None:
        """Initialize all sub-mappers"""
        self.eq_mapper = EQParameterMapper()
        self.dynamics_mapper = DynamicsParameterMapper()
        self.level_mapper = LevelParameterMapper()
        self.harmonic_mapper = HarmonicParameterMapper()

    def generate_mastering_parameters(
        self,
        fingerprint: Dict[str, Any],
        target_lufs: Optional[float] = None,
        enable_multiband: bool = False
    ) -> Dict[str, Any]:
        """
        Generate complete mastering parameters from 25D fingerprint

        Args:
            fingerprint: 25D fingerprint dictionary
            target_lufs: Target loudness level (default: -16.0)
            enable_multiband: Enable multiband dynamics (default: False)

        Returns:
            Complete parameter set for HybridProcessor
        """
        debug("Generating mastering parameters from 25D fingerprint")

        params = {
            'eq': self._generate_eq_params(fingerprint),
            'dynamics': self._generate_dynamics_params(fingerprint, enable_multiband),
            'level': self.level_mapper.map_to_level_matching(fingerprint, target_lufs),
            'harmonic': self.harmonic_mapper.map_to_harmonic_enhancement(fingerprint),
            'metadata': {
                'fingerprint_version': '25D',
                'mapper_version': '1.0',
                'source': 'adaptive_mastering'
            }
        }

        info(f"Generated parameters: EQ ({len(params['eq']['gains'])} bands), "
             f"Dynamics (ratio={params['dynamics']['standard']['ratio']:.1f}:1), "
             f"Level (gain={params['level']['gain']:+.1f}dB)")

        return params

    def _generate_eq_params(self, fingerprint: Dict[str, Any]) -> Dict[str, Any]:
        """Generate EQ parameters from frequency fingerprint"""
        freq_gains: Dict[int, float] = self.eq_mapper.map_frequency_to_eq(fingerprint)
        spectral_gains: Dict[int, float] = self.eq_mapper.map_spectral_to_eq(fingerprint)

        # Merge gains (spectral adjustments on top of frequency mapping)
        all_gains: Dict[int, float] = freq_gains.copy()
        for band, gain in spectral_gains.items():
            if band in all_gains:
                all_gains[band] += gain * 0.5  # Weight spectral adjustments lower
            else:
                all_gains[band] = gain

        # Phase 2.5.1: Apply non-linear saturation to prevent extreme values
        # Nominal range: ±12dB (typical mastering), Hard limit: ±18dB
        saturated_gains = self.eq_mapper._apply_gain_saturation(
            all_gains,
            nominal_max=12.0,
            hard_max=18.0
        )

        return {
            'enabled': True,
            'type': '31-band',
            'gains': saturated_gains
        }

    def _generate_dynamics_params(self, fingerprint: Dict[str, Any], enable_multiband: bool) -> Dict[str, Any]:
        """Generate dynamics parameters"""
        standard: Dict[str, float] = self.dynamics_mapper.map_to_compressor(fingerprint)

        params: Dict[str, Any] = {
            'enabled': True,
            'standard': standard
        }

        if enable_multiband:
            params['multiband'] = self.dynamics_mapper.map_to_multiband(fingerprint)

        return params
