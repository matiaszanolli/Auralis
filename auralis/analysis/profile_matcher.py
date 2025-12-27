"""
Profile Matcher

Matches analyzed audio content to one of the 7 mastering profiles and
generates adaptive processing targets.

Never assumes based on genre labels - only uses audio analysis.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .fingerprint.common_metrics import MetricUtils

logger = logging.getLogger(__name__)


class ProfileMatcher:
    """
    Matches audio content to mastering profiles and generates targets.

    Profiles:
    - steven_wilson_2021: Balanced audiophile (-18.3 LUFS, 18.5 dB crest)
    - steven_wilson_2024: Ultra-audiophile (-21.0 LUFS, 21.1 dB crest)
    - acdc_highway_to_hell: Classic rock (-15.6 LUFS, 17.7 dB crest, mid-dominant)
    - blind_guardian: Modern metal (-16.0 LUFS, 16.0 dB crest)
    - bob_marley_legend: Reggae (-11.0 LUFS, 12.3 dB crest)
    - joe_satriani: Loudness war rock (-10.6 LUFS, 10.5 dB crest)
    - dio_holy_diver: Maximum loudness (-8.6 LUFS, 11.6 dB crest)
    """

    def __init__(self, profiles_dir: Optional[Path] = None) -> None:
        """
        Initialize profile matcher.

        Args:
            profiles_dir: Directory containing profile JSON files
        """
        if profiles_dir is None:
            # Default to profiles/ in project root
            profiles_dir = Path(__file__).parent.parent.parent / 'profiles'

        self.profiles_dir = Path(profiles_dir)
        self.profiles = self._load_profiles()

        logger.info(f"Loaded {len(self.profiles)} mastering profiles")

    def _load_profiles(self) -> Dict[str, Any]:
        """Load all profile JSON files."""
        profiles = {}

        profile_files = {
            'steven_wilson_2021': 'steven_wilson_prodigal_2021.json',
            'steven_wilson_2024': 'steven_wilson_normal_2024.json',
            'acdc_highway_to_hell': 'acdc_highway_to_hell_2003.json',
            'blind_guardian': 'power_metal_blind_guardian.json',
            'bob_marley_legend': 'bob_marley_legend_2002.json',
            'joe_satriani': 'joe_satriani_cant_go_back_2014.json',
            'dio_holy_diver': 'dio_holy_diver_2005.json'
        }

        for profile_key, filename in profile_files.items():
            filepath = self.profiles_dir / filename
            if filepath.exists():
                with open(filepath, 'r') as f:
                    profiles[profile_key] = json.load(f)
                logger.debug(f"Loaded profile: {profile_key}")
            else:
                logger.warning(f"Profile not found: {filepath}")

        return profiles

    def get_profile(self, profile_key: str) -> Optional[Dict[str, Any]]:
        """Get a specific profile by key."""
        return self.profiles.get(profile_key)

    def generate_target(self, content_analysis: Dict[str, Any],
                       preserve_character: bool = True,
                       user_preference: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate processing target based on content analysis.

        Args:
            content_analysis: Output from ContentAwareAnalyzer
            preserve_character: If True, adjust target to preserve source character
            user_preference: Optional user override ('audiophile', 'balanced', 'loud')

        Returns:
            Processing target dict with:
            - target_lufs: Target loudness
            - min_crest_factor: Minimum dynamic range to preserve
            - frequency_target: Target frequency response
            - processing_intensity: How aggressive to process (0-1)
        """
        # Get matched profile
        profile_key = content_analysis['profile_match']
        confidence = content_analysis['confidence']
        profile: Optional[Dict[str, Any]] = self.get_profile(profile_key)

        if profile is None:
            logger.warning(f"Profile {profile_key} not found, using default")
            profile = self.get_profile('steven_wilson_2021')
            profile_key = 'steven_wilson_2021'

        # Type narrowing: profile should not be None after default handling
        if profile is None:
            raise ValueError(f"Failed to load default profile 'steven_wilson_2021'")

        # Get source characteristics
        source_spectral = content_analysis['spectral']
        source_dynamic = content_analysis['dynamic']

        # User preference override
        if user_preference:
            profile_key, profile_opt = self._apply_user_preference(
                user_preference, source_dynamic, source_spectral
            )
            if profile_opt is not None:
                profile = profile_opt
            logger.info(f"User preference '{user_preference}' → profile '{profile_key}'")

        # Base target from profile
        target_lufs = profile['loudness']['estimated_lufs']
        target_crest = profile['loudness']['crest_factor_db']

        # Adjust target based on source characteristics if preserving character
        if preserve_character:
            target_lufs, target_crest = self._adjust_for_character_preservation(
                target_lufs, target_crest, source_dynamic, source_spectral, profile_key
            )

        # Determine processing intensity
        processing_intensity = self._calculate_processing_intensity(
            source_dynamic, target_lufs, target_crest, confidence
        )

        # Frequency target
        frequency_target = {
            'bass_pct': profile['frequency_response']['bass_pct'],
            'mid_pct': profile['frequency_response']['mid_pct'],
            'high_pct': profile['frequency_response']['high_pct'],
            'bass_to_mid_db': profile['frequency_response']['bass_to_mid_db'],
            'high_to_mid_db': profile['frequency_response']['high_to_mid_db']
        }

        return {
            'profile_key': profile_key,
            'confidence': confidence,
            'target_lufs': target_lufs,
            'min_crest_factor': target_crest,
            'frequency_target': frequency_target,
            'processing_intensity': processing_intensity,
            'preserve_character': preserve_character,
            'adjustments_made': self._describe_adjustments(
                source_dynamic, target_lufs, target_crest, profile_key
            )
        }

    def _apply_user_preference(self, preference: str, source_dynamic: Dict[str, Any],
                              source_spectral: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Apply user preference override.

        Returns:
            (profile_key, profile)
        """
        if preference == 'audiophile':
            # Use quietest, most dynamic profile
            profile_key = 'steven_wilson_2024'
        elif preference == 'loud':
            # Use loudest profile
            profile_key = 'dio_holy_diver'
        elif preference == 'balanced':
            # Use moderate profile
            profile_key = 'blind_guardian'
        else:
            # Unknown preference, use content-aware default
            logger.warning(f"Unknown preference '{preference}', using content-aware")
            profile_key = 'steven_wilson_2021'

        return profile_key, self.get_profile(profile_key)

    def _adjust_for_character_preservation(self, target_lufs: float, target_crest: float,
                                          source_dynamic: Dict[str, Any], source_spectral: Dict[str, Any],
                                          profile_key: str) -> Tuple[float, float]:
        """
        Adjust target to preserve source character.

        Key principle: Don't change too drastically - preserve the artist's intent.
        """
        source_lufs = source_dynamic['estimated_lufs']
        source_crest = source_dynamic['crest_factor_db']

        # Calculate proposed change
        lufs_change = target_lufs - source_lufs
        crest_change = target_crest - source_crest

        # Limit extreme changes (preserve character)
        MAX_LUFS_CHANGE = 6.0  # Don't change loudness by more than 6 dB
        MAX_CREST_CHANGE = 4.0  # Don't change dynamics by more than 4 dB

        if abs(lufs_change) > MAX_LUFS_CHANGE:
            # Limit the change
            adjusted_lufs = source_lufs + np.sign(lufs_change) * MAX_LUFS_CHANGE
            logger.info(f"Limiting LUFS change from {lufs_change:.1f} dB to {MAX_LUFS_CHANGE:.1f} dB")
        else:
            adjusted_lufs = target_lufs

        if abs(crest_change) > MAX_CREST_CHANGE:
            # Limit the change
            adjusted_crest = source_crest + np.sign(crest_change) * MAX_CREST_CHANGE
            logger.info(f"Limiting crest change from {crest_change:.1f} dB to {MAX_CREST_CHANGE:.1f} dB")
        else:
            adjusted_crest = target_crest

        # Special case: If source is already very dynamic, don't reduce dynamics
        if source_crest > 16 and adjusted_crest < source_crest:
            logger.info(f"Source has excellent dynamics ({source_crest:.1f} dB), preserving")
            adjusted_crest = source_crest

        return adjusted_lufs, adjusted_crest

    def _calculate_processing_intensity(self, source_dynamic: Dict[str, Any], target_lufs: float,
                                       target_crest: float, confidence: float) -> float:
        """
        Calculate how aggressive the processing should be.

        Returns:
            Intensity value 0.0 to 1.0:
            - 0.0-0.3: Gentle processing (source close to target)
            - 0.3-0.6: Moderate processing
            - 0.6-0.9: Aggressive processing (source far from target)
            - 0.9-1.0: Maximum processing (extreme cases)
        """
        source_lufs = source_dynamic['estimated_lufs']
        source_crest = source_dynamic['crest_factor_db']

        # Calculate distance from target
        lufs_distance = abs(target_lufs - source_lufs)
        crest_distance = abs(target_crest - source_crest)

        # Normalize distances (0-1 scale) using MetricUtils
        # LUFS: 0-10 dB difference → 0-1
        lufs_norm = MetricUtils.normalize_to_range(lufs_distance, 10.0, clip=True)
        # Crest: 0-8 dB difference → 0-1
        crest_norm = MetricUtils.normalize_to_range(crest_distance, 8.0, clip=True)

        # Combine (weighted: LUFS more important)
        intensity = (lufs_norm * 0.6 + crest_norm * 0.4)

        # Adjust for confidence (lower confidence = gentler processing)
        intensity *= (0.5 + confidence * 0.5)

        # Clamp to 0-1 using MetricUtils for consistency
        intensity = MetricUtils.normalize_to_range(intensity, 1.0, clip=True)

        logger.info(f"Processing intensity: {intensity:.2f} "
                   f"(LUFS dist: {lufs_distance:.1f} dB, Crest dist: {crest_distance:.1f} dB, "
                   f"Confidence: {confidence:.2f})")

        return intensity

    def _describe_adjustments(self, source_dynamic: Dict[str, Any], target_lufs: float,
                            target_crest: float, profile_key: str) -> str:
        """Generate human-readable description of adjustments."""
        source_lufs = source_dynamic['estimated_lufs']
        source_crest = source_dynamic['crest_factor_db']

        lufs_change = target_lufs - source_lufs
        crest_change = target_crest - source_crest

        parts = []

        # Loudness adjustment
        if abs(lufs_change) < 1:
            parts.append("minimal loudness adjustment")
        elif lufs_change < -3:
            parts.append(f"significant volume reduction ({lufs_change:.1f} dB)")
        elif lufs_change < 0:
            parts.append(f"moderate volume reduction ({lufs_change:.1f} dB)")
        elif lufs_change > 3:
            parts.append(f"significant volume increase (+{lufs_change:.1f} dB)")
        else:
            parts.append(f"moderate volume increase (+{lufs_change:.1f} dB)")

        # Dynamic range adjustment
        if abs(crest_change) < 1:
            parts.append("dynamics preserved")
        elif crest_change < -2:
            parts.append(f"dynamics reduced ({crest_change:.1f} dB)")
        elif crest_change < 0:
            parts.append(f"dynamics slightly reduced ({crest_change:.1f} dB)")
        elif crest_change > 2:
            parts.append(f"dynamics enhanced (+{crest_change:.1f} dB)")
        else:
            parts.append(f"dynamics slightly enhanced (+{crest_change:.1f} dB)")

        # Profile reference
        parts.append(f"using {profile_key.replace('_', ' ')} reference")

        return ", ".join(parts)

    def get_all_profile_keys(self) -> List[str]:
        """Get list of all available profile keys."""
        return list(self.profiles.keys())

    def compare_to_profile(self, content_analysis: Dict[str, Any], profile_key: str) -> Dict[str, Any]:
        """
        Compare source audio to a specific profile.

        Returns:
            Comparison dict with differences
        """
        profile = self.get_profile(profile_key)
        if profile is None:
            return {'error': f'Profile {profile_key} not found'}

        source_spectral = content_analysis['spectral']
        source_dynamic = content_analysis['dynamic']

        return {
            'profile_key': profile_key,
            'lufs_difference': profile['loudness']['estimated_lufs'] - source_dynamic['estimated_lufs'],
            'crest_difference': profile['loudness']['crest_factor_db'] - source_dynamic['crest_factor_db'],
            'bass_pct_difference': profile['frequency_response']['bass_pct'] - source_spectral['bass_pct'],
            'mid_pct_difference': profile['frequency_response']['mid_pct'] - source_spectral['mid_pct'],
            'bass_mid_ratio_difference': profile['frequency_response']['bass_to_mid_db'] - source_spectral['bass_to_mid_db']
        }
