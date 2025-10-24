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
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass


@dataclass
class SpectrumPosition:
    """
    Position on the multi-dimensional processing spectrum.
    Each dimension ranges from 0.0 to 1.0.
    """
    # Input level dimension: 0.0 = very quiet, 1.0 = very loud
    input_level: float

    # Dynamic range dimension: 0.0 = highly compressed, 1.0 = very dynamic
    dynamic_range: float

    # Spectral balance: 0.0 = very dark, 1.0 = very bright
    spectral_balance: float

    # Energy level: 0.0 = calm/ambient, 1.0 = energetic/aggressive
    energy: float

    # Density: 0.0 = sparse/simple, 1.0 = dense/complex
    density: float


@dataclass
class ProcessingParameters:
    """
    Calculated processing parameters from spectrum analysis.
    These flow naturally from content, not rigid presets.
    """
    # EQ parameters (dB)
    bass_adjustment: float
    low_mid_adjustment: float
    mid_adjustment: float
    high_mid_adjustment: float
    treble_adjustment: float

    # Dynamics parameters
    compression_ratio: float
    compression_threshold: float
    compression_amount: float  # 0.0-1.0 blend

    limiter_threshold: float
    limiter_amount: float  # 0.0-1.0 blend

    # Gain staging
    input_gain: float
    output_target_rms: float  # Target RMS level

    # Processing intensity
    eq_intensity: float  # 0.0-1.0
    dynamics_intensity: float  # 0.0-1.0


class SpectrumMapper:
    """
    Maps content analysis to processing parameters using spectrum-based approach.
    Presets provide anchor points for interpolation.
    """

    def __init__(self):
        """Initialize spectrum mapper with preset anchor points."""
        self.preset_anchors = self._define_preset_anchors()

    def _define_preset_anchors(self) -> Dict[str, Tuple[SpectrumPosition, ProcessingParameters]]:
        """
        Define presets as anchor points on the spectrum.
        Each preset has a position and corresponding parameters.
        """
        return {
            'gentle': (
                SpectrumPosition(
                    input_level=0.6,  # Well-leveled
                    dynamic_range=0.8,  # Preserve dynamics
                    spectral_balance=0.6,  # Balanced, slightly bright
                    energy=0.4,  # Moderate energy
                    density=0.5,  # Medium complexity
                ),
                ProcessingParameters(
                    bass_adjustment=0.3,
                    low_mid_adjustment=0.0,
                    mid_adjustment=0.0,
                    high_mid_adjustment=0.2,
                    treble_adjustment=0.5,
                    compression_ratio=1.8,
                    compression_threshold=-20.0,
                    compression_amount=0.5,
                    limiter_threshold=-2.0,
                    limiter_amount=0.5,
                    input_gain=0.0,
                    output_target_rms=-15.0,
                    eq_intensity=0.6,
                    dynamics_intensity=0.5,
                )
            ),

            'punchy': (
                SpectrumPosition(
                    input_level=0.5,  # Moderate level
                    dynamic_range=0.5,  # Controlled dynamics
                    spectral_balance=0.6,  # Balanced with presence
                    energy=0.8,  # High energy
                    density=0.7,  # Complex/busy
                ),
                ProcessingParameters(
                    bass_adjustment=1.8,
                    low_mid_adjustment=0.5,
                    mid_adjustment=0.0,
                    high_mid_adjustment=1.5,
                    treble_adjustment=0.8,
                    compression_ratio=2.5,
                    compression_threshold=-18.0,
                    compression_amount=0.65,
                    limiter_threshold=-2.0,
                    limiter_amount=0.65,
                    input_gain=0.0,
                    output_target_rms=-14.0,
                    eq_intensity=0.75,
                    dynamics_intensity=0.65,
                )
            ),

            'live': (
                SpectrumPosition(
                    input_level=0.7,  # Often hot peaks
                    dynamic_range=0.7,  # High crest factor
                    spectral_balance=0.5,  # Varies, often muddy
                    energy=0.7,  # High energy
                    density=0.6,  # Moderate complexity
                ),
                ProcessingParameters(
                    bass_adjustment=0.8,
                    low_mid_adjustment=-0.8,  # Reduce mud
                    mid_adjustment=0.5,
                    high_mid_adjustment=2.0,  # Clarity
                    treble_adjustment=1.5,
                    compression_ratio=1.8,
                    compression_threshold=-22.0,
                    compression_amount=0.4,
                    limiter_threshold=-3.5,
                    limiter_amount=0.4,
                    input_gain=0.0,
                    output_target_rms=-11.5,  # INCREASED from -13.5 for high-energy live material
                    eq_intensity=0.7,
                    dynamics_intensity=0.4,
                )
            ),

            'adaptive': (
                SpectrumPosition(
                    input_level=0.5,  # Center/neutral
                    dynamic_range=0.8,  # Prefer preserving dynamics
                    spectral_balance=0.5,  # Neutral
                    energy=0.5,  # Neutral
                    density=0.5,  # Neutral
                ),
                ProcessingParameters(
                    bass_adjustment=0.0,
                    low_mid_adjustment=0.0,
                    mid_adjustment=0.0,
                    high_mid_adjustment=0.0,
                    treble_adjustment=0.0,
                    compression_ratio=1.5,
                    compression_threshold=-26.0,
                    compression_amount=0.25,
                    limiter_threshold=-4.0,
                    limiter_amount=0.25,
                    input_gain=0.0,
                    output_target_rms=-16.0,
                    eq_intensity=0.4,
                    dynamics_intensity=0.25,
                )
            ),
        }

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

        # Interpolate parameters using weighted blend
        result = ProcessingParameters(
            bass_adjustment=0.0,
            low_mid_adjustment=0.0,
            mid_adjustment=0.0,
            high_mid_adjustment=0.0,
            treble_adjustment=0.0,
            compression_ratio=0.0,
            compression_threshold=0.0,
            compression_amount=0.0,
            limiter_threshold=0.0,
            limiter_amount=0.0,
            input_gain=0.0,
            output_target_rms=0.0,
            eq_intensity=0.0,
            dynamics_intensity=0.0,
        )

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
            result.limiter_threshold += anchor_params.limiter_threshold * weight
            result.limiter_amount += anchor_params.limiter_amount * weight
            result.input_gain += anchor_params.input_gain * weight
            result.output_target_rms += anchor_params.output_target_rms * weight
            result.eq_intensity += anchor_params.eq_intensity * weight
            result.dynamics_intensity += anchor_params.dynamics_intensity * weight

        # Apply content-specific modifiers
        result = self._apply_content_modifiers(result, spectrum_position)

        return result

    def _apply_content_modifiers(self,
                                 params: ProcessingParameters,
                                 position: SpectrumPosition) -> ProcessingParameters:
        """
        Apply content-specific modifiers to interpolated parameters.
        These are rules that apply across the spectrum.
        """
        # Rule 1: Very dynamic material (high crest) needs less compression
        # BUT: High-energy dynamic material (metal) can still handle processing
        if position.dynamic_range > 0.75:
            if position.energy < 0.6:
                # Low energy + high dynamics (classical/jazz) - very gentle
                params.compression_amount *= 0.5
                params.dynamics_intensity *= 0.6
            else:
                # High energy + high dynamics (metal/live) - moderate reduction
                params.compression_amount *= 0.8
                params.dynamics_intensity *= 0.9

        # Rule 2: Very quiet material needs input gain
        if position.input_level < 0.3:  # RMS < -24 dB
            params.input_gain = (0.3 - position.input_level) * 20.0  # Up to +6 dB
            params.input_gain = min(params.input_gain, 12.0)  # Cap at +12 dB

        # Rule 3: Very bright material needs treble reduction
        if position.spectral_balance > 0.8:
            params.treble_adjustment *= 0.5
            params.high_mid_adjustment *= 0.7

        # Rule 4: Very dark material needs brightness enhancement
        if position.spectral_balance < 0.3:
            params.treble_adjustment += 1.0
            params.high_mid_adjustment += 0.8

        # Rule 5: High energy material can handle more aggressive processing
        if position.energy > 0.7:
            params.dynamics_intensity *= 1.2
            params.eq_intensity *= 1.1

        # Rule 6: Adjust output target based on input level and dynamics
        # Quiet + dynamic = conservative boost
        # Loud + compressed = gentle control
        if position.input_level < 0.4 and position.dynamic_range > 0.6:
            # Quiet but dynamic (like classical) - moderate boost
            params.output_target_rms = -16.0
        elif position.input_level > 0.8:
            # CRITICAL: Very loud material (like Testament) - needs energy boost
            # Despite already being loud, these need RMS increase for competitive loudness
            params.output_target_rms = -11.0  # INCREASED from -11.5 to account for peak normalization loss
            print(f"[Content Rule] Very Loud detected (Level:{position.input_level:.2f}) → Target RMS -11.0 dB")
        elif position.input_level > 0.7 and position.dynamic_range > 0.4:
            # Loud + some dynamics (like live recordings) - bring up RMS
            params.output_target_rms = -12.0
            print(f"[Content Rule] Loud+Dynamic detected (Level:{position.input_level:.2f}, DR:{position.dynamic_range:.2f}) → Target RMS -12.0 dB")
        elif position.input_level > 0.6 and position.dynamic_range > 0.5:
            # Moderately loud + dynamic - still needs some boost
            params.output_target_rms = -13.0
        elif position.input_level < 0.3:
            # Very quiet - significant boost needed
            params.output_target_rms = -14.0

        return params
