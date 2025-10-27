"""
Continuous Target Generator

Instead of matching to discrete profiles, this generates targets by treating
audio characteristics as continuous variables in a multi-dimensional space.

Philosophy:
- Audio characteristics exist on continuous spectrums, not in discrete buckets
- Target parameters are computed dynamically based on input measurements
- No "if genre == X then Y" logic - pure mathematical relationships
- The 7 profiles are reference points that inform the parameter space, not templates

Multi-Dimensional Parameter Space:
1. Loudness Dimension: LUFS (-21 to -8 dB range observed)
2. Dynamics Dimension: Crest Factor (10.5 to 21.1 dB range observed)
3. Frequency Balance: Bass/Mid Ratio (-3.4 to +5.5 dB range observed)
4. Spectral Distribution: Bass%, Mid%, High% (continuous)
5. Era/Compression: Inferred from dynamics and loudness relationship

Based on 7 reference points analysis (October 26, 2025):
- Discovered relationships, not categories
- Parameters are correlated (not independent)
- Smooth transitions between extremes
"""

import numpy as np
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ContinuousTargetGenerator:
    """
    Generates processing targets using continuous parameter space.

    No profile matching - pure mathematical relationships derived from
    analysis of 7 diverse reference recordings.
    """

    def __init__(self):
        """Initialize with parameter space bounds from reference analysis."""

        # Observed ranges from 7 references (these define our parameter space)
        self.bounds = {
            'lufs': {'min': -21.0, 'max': -8.6, 'neutral': -15.0},
            'crest': {'min': 10.5, 'max': 21.1, 'neutral': 16.0},
            'bass_mid_ratio': {'min': -3.4, 'max': 5.5, 'neutral': 1.0},
            'bass_pct': {'min': 30.9, 'max': 74.6, 'neutral': 55.0},
            'mid_pct': {'min': 21.3, 'max': 66.9, 'neutral': 35.0}
        }

        # Key discovery: Crest and LUFS are INVERSELY correlated
        # High crest → Low LUFS (audiophile)
        # Low crest → High LUFS (loudness war)
        self.dynamics_loudness_correlation = -0.85  # Strong inverse correlation

    def generate_target(self,
                       audio_analysis: Dict,
                       user_intent: Optional[str] = None,
                       preserve_character: float = 0.7) -> Dict:
        """
        Generate processing target from continuous parameter space.

        Args:
            audio_analysis: Content analysis (spectral, dynamic, energy)
            user_intent: Optional user guidance ('enhance', 'preserve', 'transform')
            preserve_character: How much to preserve source (0=transform fully, 1=preserve exactly)
                               Default 0.7 = mostly preserve, enhance slightly

        Returns:
            Continuous target parameters (not a discrete profile!)
        """
        spectral = audio_analysis['spectral']
        dynamic = audio_analysis['dynamic']

        # Extract source characteristics
        source_lufs = dynamic['estimated_lufs']
        source_crest = dynamic['crest_factor_db']
        source_bass_mid = spectral['bass_to_mid_db']
        source_bass_pct = spectral['bass_pct']
        source_mid_pct = spectral['mid_pct']

        # Determine optimal targets based on continuous relationships
        target_params = self._compute_optimal_targets(
            source_lufs, source_crest, source_bass_mid,
            source_bass_pct, source_mid_pct
        )

        # Apply user intent modifier
        if user_intent:
            target_params = self._apply_user_intent(target_params, user_intent)

        # Blend source and target based on preserve_character
        final_params = self._blend_source_target(
            {
                'lufs': source_lufs,
                'crest': source_crest,
                'bass_mid_ratio': source_bass_mid,
                'bass_pct': source_bass_pct,
                'mid_pct': source_mid_pct
            },
            target_params,
            preserve_character
        )

        # Calculate processing intensity from parameter deltas
        intensity = self._calculate_intensity_from_deltas(
            source_lufs, source_crest, source_bass_mid,
            final_params['lufs'], final_params['crest'], final_params['bass_mid_ratio']
        )

        logger.info(f"Continuous target: LUFS {source_lufs:.1f}→{final_params['lufs']:.1f}, "
                   f"Crest {source_crest:.1f}→{final_params['crest']:.1f}, "
                   f"B/M {source_bass_mid:+.1f}→{final_params['bass_mid_ratio']:+.1f}, "
                   f"Intensity {intensity:.2f}")

        return {
            'target_lufs': final_params['lufs'],
            'target_crest_factor': final_params['crest'],
            'target_bass_mid_ratio': final_params['bass_mid_ratio'],
            'target_bass_pct': final_params['bass_pct'],
            'target_mid_pct': final_params['mid_pct'],
            'processing_intensity': intensity,
            'preserve_character': preserve_character,
            'source_characteristics': {
                'lufs': source_lufs,
                'crest': source_crest,
                'bass_mid_ratio': source_bass_mid
            },
            'deltas': {
                'lufs_change': final_params['lufs'] - source_lufs,
                'crest_change': final_params['crest'] - source_crest,
                'bass_mid_change': final_params['bass_mid_ratio'] - source_bass_mid
            }
        }

    def _compute_optimal_targets(self,
                                 source_lufs: float,
                                 source_crest: float,
                                 source_bass_mid: float,
                                 source_bass_pct: float,
                                 source_mid_pct: float) -> Dict:
        """
        Compute optimal targets based on discovered relationships.

        Key Insights from 7-reference analysis:
        1. High dynamics (>17 dB crest) → Keep or enhance dynamics
        2. Low dynamics (<12 dB crest) → Opportunity to restore dynamics
        3. Mid-dominant (>50% mid) → Rare classic sound, preserve it
        4. Extreme bass (>70%) → Modern sound, may need rebalancing
        5. LUFS and Crest are inversely correlated
        """

        # Target dynamics based on source dynamics quality
        if source_crest > 17:
            # Source has excellent dynamics - preserve or enhance slightly
            target_crest = source_crest + 0.5  # Slight enhancement
            target_crest = min(target_crest, self.bounds['crest']['max'])

        elif source_crest < 12:
            # Source is heavily compressed - restore some dynamics
            # But don't go crazy - respect the artistic intent somewhat
            improvement = (self.bounds['crest']['neutral'] - source_crest) * 0.5
            target_crest = source_crest + improvement

        else:
            # Source has moderate dynamics - aim for balanced improvement
            target_crest = self.bounds['crest']['neutral']

        # Target loudness based on dynamics (inverse correlation)
        # High dynamics → Lower LUFS (audiophile approach)
        # Low dynamics → Higher LUFS (but still reasonable)
        normalized_crest = (target_crest - self.bounds['crest']['min']) / \
                          (self.bounds['crest']['max'] - self.bounds['crest']['min'])

        # Inverse relationship: high crest → low LUFS
        target_lufs = self.bounds['lufs']['max'] - \
                     normalized_crest * (self.bounds['lufs']['max'] - self.bounds['lufs']['min'])

        # Target frequency balance based on source characteristics
        if source_mid_pct > 50 and source_bass_mid < 0:
            # Classic mid-dominant sound - PRESERVE IT (rare and valuable)
            target_bass_mid = source_bass_mid
            target_bass_pct = source_bass_pct
            target_mid_pct = source_mid_pct
            logger.info("Detected classic mid-dominant sound - preserving frequency balance")

        elif source_bass_pct > 70:
            # Extreme modern bass-heavy - may benefit from slight rebalancing
            target_bass_pct = source_bass_pct - 5  # Reduce bass slightly
            target_mid_pct = source_mid_pct + 3   # Increase mids slightly
            target_bass_mid = source_bass_mid - 0.5
            logger.info("Extreme bass detected - applying gentle rebalancing")

        else:
            # Normal range - slight enhancement toward balanced
            # Move 30% toward neutral, preserve 70%
            target_bass_mid = source_bass_mid * 0.7 + self.bounds['bass_mid_ratio']['neutral'] * 0.3
            target_bass_pct = source_bass_pct * 0.7 + self.bounds['bass_pct']['neutral'] * 0.3
            target_mid_pct = source_mid_pct * 0.7 + self.bounds['mid_pct']['neutral'] * 0.3

        return {
            'lufs': target_lufs,
            'crest': target_crest,
            'bass_mid_ratio': target_bass_mid,
            'bass_pct': target_bass_pct,
            'mid_pct': target_mid_pct
        }

    def _apply_user_intent(self, target_params: Dict, intent: str) -> Dict:
        """
        Modify targets based on user intent.

        Intent modifiers (not rigid categories!):
        - 'enhance': Slight improvement, stay close to source
        - 'preserve': Minimal changes, only fix problems
        - 'transform': Larger changes allowed
        - 'audiophile': Push toward high-dynamics end of spectrum
        - 'punchy': Push toward more impact (moderate compression)
        """
        modified = target_params.copy()

        if intent == 'audiophile':
            # Push toward high-dynamics end of spectrum
            modified['crest'] = min(modified['crest'] + 2.0, self.bounds['crest']['max'])
            modified['lufs'] = max(modified['lufs'] - 2.0, self.bounds['lufs']['min'])

        elif intent == 'punchy':
            # Push toward more impact (but not loudness war levels)
            modified['crest'] = max(modified['crest'] - 1.5, 14.0)  # Keep above 14 dB
            modified['lufs'] = min(modified['lufs'] + 2.0, -12.0)   # Keep below -12 LUFS

        elif intent == 'preserve':
            # Scale back changes by 50%
            for key in ['crest', 'lufs', 'bass_mid_ratio']:
                modified[key] = target_params[key] * 0.5 + modified[key] * 0.5

        # 'enhance' and 'transform' use defaults (no modification)

        return modified

    def _blend_source_target(self,
                            source: Dict,
                            target: Dict,
                            preserve: float) -> Dict:
        """
        Blend source and target parameters based on preservation amount.

        preserve=1.0: Keep source exactly
        preserve=0.0: Use target fully
        preserve=0.7: 70% source, 30% target (default)
        """
        blended = {}

        for key in target.keys():
            if key in source:
                blended[key] = source[key] * preserve + target[key] * (1.0 - preserve)
            else:
                blended[key] = target[key]

        return blended

    def _calculate_intensity_from_deltas(self,
                                        source_lufs: float,
                                        source_crest: float,
                                        source_bass_mid: float,
                                        target_lufs: float,
                                        target_crest: float,
                                        target_bass_mid: float) -> float:
        """
        Calculate processing intensity from parameter deltas.

        Larger changes → Higher intensity
        Returns: 0.0 to 1.0
        """
        # Normalize deltas to 0-1 scale
        lufs_delta = abs(target_lufs - source_lufs) / 10.0  # 10 dB max expected
        crest_delta = abs(target_crest - source_crest) / 8.0  # 8 dB max expected
        freq_delta = abs(target_bass_mid - source_bass_mid) / 5.0  # 5 dB max expected

        # Weighted combination (dynamics most important)
        intensity = (
            lufs_delta * 0.35 +
            crest_delta * 0.45 +
            freq_delta * 0.20
        )

        # Clamp to 0-1
        return np.clip(intensity, 0.0, 1.0)

    def get_parameter_space_info(self) -> Dict:
        """
        Get information about the multi-dimensional parameter space.

        Useful for visualization and understanding the continuous space.
        """
        return {
            'dimensions': 5,
            'dimension_names': ['LUFS', 'Crest Factor', 'Bass/Mid Ratio', 'Bass %', 'Mid %'],
            'bounds': self.bounds,
            'relationships': {
                'lufs_crest_correlation': self.dynamics_loudness_correlation,
                'description': 'High dynamics → Low LUFS (inverse correlation)'
            },
            'reference_points': 7,
            'approach': 'continuous interpolation, not discrete matching'
        }


def generate_adaptive_target(audio_analysis: Dict,
                            user_intent: Optional[str] = None,
                            preserve_character: float = 0.7) -> Dict:
    """
    Convenience function for continuous target generation.

    Args:
        audio_analysis: Content analysis from ContentAwareAnalyzer
        user_intent: Optional user guidance
        preserve_character: 0-1, how much to preserve source

    Returns:
        Continuous target parameters
    """
    generator = ContinuousTargetGenerator()
    return generator.generate_target(audio_analysis, user_intent, preserve_character)
