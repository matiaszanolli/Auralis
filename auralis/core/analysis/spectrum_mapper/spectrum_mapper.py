#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Spectrum-Based Processing Mapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Maps content analysis to processing parameters using a spectrum-based approach.
Presets act as anchor points rather than rigid configurations.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any, Tuple

from .data_classes import SpectrumPosition, ProcessingParameters
from .preset_anchors import get_preset_anchors
from .content_modifiers import apply_content_modifiers


class SpectrumMapper:
    """
    Maps content analysis to processing parameters using spectrum-based approach.
    Presets provide anchor points for interpolation.
    """

    def __init__(self) -> None:
        """Initialize spectrum mapper with preset anchor points."""
        self.preset_anchors = get_preset_anchors()

    def analyze_to_spectrum_position(self, content_profile: Dict[str, Any]) -> SpectrumPosition:
        """
        Convert content analysis to a position on the processing spectrum.

        Args:
            content_profile: Content analysis dictionary from ContentAnalyzer

        Returns:
            SpectrumPosition representing the content characteristics
        """
        # Extract relevant metrics
        input_level_info = content_profile.get('input_level_info', {})
        rms_db = input_level_info.get('rms_db', -15.0)
        crest_db = input_level_info.get('crest_db', 12.0)

        spectral_centroid = content_profile.get('spectral_centroid', 2000)
        energy_level = content_profile.get('energy_level', 'medium')
        dynamic_range = content_profile.get('dynamic_range', 20.0)

        # Map to 0.0-1.0 scales

        # Input level: -30 dB (very quiet) = 0.0, -10 dB (very loud) = 1.0
        input_level = np.clip((rms_db + 30.0) / 20.0, 0.0, 1.0)

        # Dynamic range: 6 dB (crushed) = 0.0, 18 dB (very dynamic) = 1.0
        dynamic_range_norm = np.clip((crest_db - 6.0) / 12.0, 0.0, 1.0)

        # Spectral balance: 1000 Hz (dark) = 0.0, 4000 Hz (bright) = 1.0
        spectral_balance = np.clip((spectral_centroid - 1000.0) / 3000.0, 0.0, 1.0)

        # Energy: low/medium/high → 0.0/0.5/1.0
        energy_map = {'low': 0.3, 'medium': 0.5, 'high': 0.8}
        energy = energy_map.get(energy_level, 0.5)

        # Density: Estimate from dynamic range and spectral characteristics
        # High dynamic range + centered spectrum = sparse (classical)
        # Low dynamic range + wide spectrum = dense (electronic/metal)
        density = 0.5 + (1.0 - dynamic_range_norm) * 0.3 + (spectral_balance - 0.5) * 0.2
        density = np.clip(density, 0.0, 1.0)

        return SpectrumPosition(
            input_level=input_level,
            dynamic_range=dynamic_range_norm,
            spectral_balance=spectral_balance,
            energy=energy,
            density=density
        )

    def calculate_processing_parameters(self,
                                       spectrum_position: SpectrumPosition,
                                       user_preset_hint: str = 'adaptive') -> ProcessingParameters:
        """
        Calculate processing parameters by interpolating on the spectrum.

        Args:
            spectrum_position: Content's position on the spectrum
            user_preset_hint: User's preset choice provides initial weighting

        Returns:
            ProcessingParameters calculated from spectrum position
        """
        # Calculate distances from each preset anchor
        weights = self._calculate_preset_weights(spectrum_position, user_preset_hint)

        # Interpolate parameters using weighted blend
        result = self._interpolate_parameters(weights)

        # Apply content-specific modifiers
        result = apply_content_modifiers(result, spectrum_position, user_preset_hint)

        return result

    def _calculate_preset_weights(self,
                                  spectrum_position: SpectrumPosition,
                                  user_preset_hint: str) -> Dict[str, float]:
        """
        Calculate weighted influence of each preset based on distance.

        Args:
            spectrum_position: Content's position on the spectrum
            user_preset_hint: User's preset choice

        Returns:
            Dictionary of normalized weights for each preset
        """
        distances = {}
        weights = {}
        total_weight = 0.0

        for preset_name, (anchor_pos, anchor_params) in self.preset_anchors.items():
            # Euclidean distance in 5D space
            dist = np.sqrt(
                (spectrum_position.input_level - anchor_pos.input_level) ** 2 +
                (spectrum_position.dynamic_range - anchor_pos.dynamic_range) ** 2 +
                (spectrum_position.spectral_balance - anchor_pos.spectral_balance) ** 2 +
                (spectrum_position.energy - anchor_pos.energy) ** 2 +
                (spectrum_position.density - anchor_pos.density) ** 2
            )

            distances[preset_name] = dist

            # Weight inversely proportional to distance (closer = more influence)
            # Add small epsilon to avoid division by zero
            weight = 1.0 / (dist + 0.1)

            # Boost weight for user's preset hint
            if preset_name == user_preset_hint:
                weight *= 2.0

            weights[preset_name] = weight
            total_weight += weight

        # Normalize weights
        for preset_name in weights:
            weights[preset_name] /= total_weight

        return weights

    def _interpolate_parameters(self, weights: Dict[str, float]) -> ProcessingParameters:
        """
        Interpolate processing parameters using weighted blend of presets.

        Args:
            weights: Normalized weights for each preset

        Returns:
            Interpolated ProcessingParameters
        """
        # Initialize result with zeros
        result = ProcessingParameters(
            bass_adjustment=0.0,
            low_mid_adjustment=0.0,
            mid_adjustment=0.0,
            high_mid_adjustment=0.0,
            treble_adjustment=0.0,
            compression_ratio=0.0,
            compression_threshold=0.0,
            compression_amount=0.0,
            expansion_amount=0.0,
            limiter_threshold=0.0,
            limiter_amount=0.0,
            input_gain=0.0,
            output_target_rms=0.0,
            eq_intensity=0.0,
            dynamics_intensity=0.0,
        )

        # Blend parameters from all presets
        for preset_name, weight in weights.items():
            _, anchor_params = self.preset_anchors[preset_name]

            result.bass_adjustment += anchor_params.bass_adjustment * weight
            result.low_mid_adjustment += anchor_params.low_mid_adjustment * weight
            result.mid_adjustment += anchor_params.mid_adjustment * weight
            result.high_mid_adjustment += anchor_params.high_mid_adjustment * weight
            result.treble_adjustment += anchor_params.treble_adjustment * weight
            result.compression_ratio += anchor_params.compression_ratio * weight
            result.compression_threshold += anchor_params.compression_threshold * weight
            result.compression_amount += anchor_params.compression_amount * weight
            result.expansion_amount += anchor_params.expansion_amount * weight
            result.limiter_threshold += anchor_params.limiter_threshold * weight
            result.limiter_amount += anchor_params.limiter_amount * weight
            result.input_gain += anchor_params.input_gain * weight
            result.output_target_rms += anchor_params.output_target_rms * weight
            result.eq_intensity += anchor_params.eq_intensity * weight
            result.dynamics_intensity += anchor_params.dynamics_intensity * weight

        return result
