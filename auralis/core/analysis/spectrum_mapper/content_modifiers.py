#!/usr/bin/env python3

"""
Content-Specific Modifiers
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rules for adjusting processing parameters based on content characteristics

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .data_classes import ProcessingParameters, SpectrumPosition


def apply_content_modifiers(params: ProcessingParameters,
                            position: SpectrumPosition,
                            user_preset_hint: str = 'adaptive') -> ProcessingParameters:
    """
    Apply content-specific modifiers to interpolated parameters.
    These are rules that apply across the spectrum.

    Args:
        params: Interpolated processing parameters
        position: Spectrum position from content analysis
        user_preset_hint: User's preset choice for blending content rules with preset targets

    Returns:
        Modified processing parameters
    """
    # Get user preset target for RMS blending
    from ...config.preset_profiles import get_preset_profile
    preset_profile = get_preset_profile(user_preset_hint)
    preset_target_lufs = preset_profile.target_lufs if preset_profile else -16.0

    # Apply all modifier rules
    params = _apply_extreme_dynamics_rule(params, position, preset_target_lufs)
    params = _apply_dynamic_material_rule(params, position)
    params = _apply_quiet_material_rule(params, position)
    params = _apply_spectral_balance_rules(params, position)
    params = _apply_energy_rules(params, position)
    params = _apply_output_target_rules(params, position, preset_target_lufs)

    return params


def _apply_extreme_dynamics_rule(params: ProcessingParameters,
                                 position: SpectrumPosition,
                                 preset_target_lufs: float) -> ProcessingParameters:
    """
    Rule 1a: Handle extreme dynamics (crest > 17 dB, DR > 0.9)

    Distinguish between:
    - Under-leveled + naturally dynamic (classical, 80s rock) → preserve dynamics, just add gain
    - Moderate level + extreme peaks (poorly mastered metal) → compress to competitive loudness
    """
    if position.dynamic_range > 0.9:
        if position.input_level < 0.45:
            # Very quiet + extreme dynamics → Classic/natural recording, preserve dynamics
            # Examples: Seru Giran (Level 0.42, Crest 21.18 dB), classical recordings
            params.compression_amount = 0.0  # NO compression, just gain
            params.dynamics_intensity = 0.0
            # Blend: Favor content rule (70%) to preserve dynamics
            content_recommended = -18.0
            params.output_target_rms = (
                content_recommended * 0.7 +
                preset_target_lufs * 0.3
            )
            print(f"[Content Rule] NATURALLY dynamic classic recording (Level:{position.input_level:.2f}, DR:{position.dynamic_range:.2f}) → Preserve dynamics, blended RMS {params.output_target_rms:.1f} dB")
        else:
            # Moderate level + extreme dynamics → Poorly mastered, needs compression
            # Example: Slayer (Level 0.50, Crest 18.98 dB)
            params.compression_amount = 0.85  # Heavy compression
            params.dynamics_intensity = 0.85
            # Blend: Conservative (30% content, 70% preset) to match Matchering behavior
            # Matchering boosts by +3-5 dB, not +11-18 dB
            content_recommended = -17.0  # More conservative
            params.output_target_rms = (
                content_recommended * 0.3 +
                preset_target_lufs * 0.7
            )
            print(f"[Content Rule] EXTREME dynamics needing correction (Level:{position.input_level:.2f}, DR:{position.dynamic_range:.2f}) → Blended RMS {params.output_target_rms:.1f} dB")

    return params


def _apply_dynamic_material_rule(params: ProcessingParameters,
                                 position: SpectrumPosition) -> ProcessingParameters:
    """
    Rule 1b: Very dynamic material (high crest) needs careful handling
    BUT: High-energy dynamic material (metal) can still handle processing
    """
    if position.dynamic_range > 0.75:
        if position.energy < 0.6:
            # Low energy + high dynamics (classical/jazz) - very gentle
            params.compression_amount *= 0.5
            params.dynamics_intensity *= 0.6
        else:
            # High energy + high dynamics (metal/live) - moderate reduction
            params.compression_amount *= 0.8
            params.dynamics_intensity *= 0.9

    return params


def _apply_quiet_material_rule(params: ProcessingParameters,
                               position: SpectrumPosition) -> ProcessingParameters:
    """
    Rule 2: Very quiet material needs input gain
    """
    if position.input_level < 0.3:  # RMS < -24 dB
        params.input_gain = (0.3 - position.input_level) * 20.0  # Up to +6 dB
        params.input_gain = min(params.input_gain, 12.0)  # Cap at +12 dB

    return params


def _apply_spectral_balance_rules(params: ProcessingParameters,
                                  position: SpectrumPosition) -> ProcessingParameters:
    """
    Rules 3-4: Adjust EQ based on spectral balance
    """
    # Rule 3: Very bright material needs treble reduction
    if position.spectral_balance > 0.8:
        params.treble_adjustment *= 0.5
        params.high_mid_adjustment *= 0.7

    # Rule 4: Very dark material needs brightness enhancement
    if position.spectral_balance < 0.3:
        params.treble_adjustment += 1.0
        params.high_mid_adjustment += 0.8

    return params


def _apply_energy_rules(params: ProcessingParameters,
                       position: SpectrumPosition) -> ProcessingParameters:
    """
    Rule 5: High energy material can handle more aggressive processing
    """
    if position.energy > 0.7:
        params.dynamics_intensity *= 1.2
        params.eq_intensity *= 1.1

    return params


def _apply_output_target_rules(params: ProcessingParameters,
                               position: SpectrumPosition,
                               preset_target_lufs: float) -> ProcessingParameters:
    """
    Rule 6: Adjust output target based on input level and dynamics
    GOAL: Better audio experience - good RMS, broader range, less compression on heavy material
    """
    # Check for problematic combinations first
    if position.input_level < 0.4 and position.dynamic_range > 0.6:
        # Quiet but dynamic (like classical) - moderate boost, preserve dynamics
        content_recommended = -16.0
        params.output_target_rms = (
            content_recommended * 0.4 +
            preset_target_lufs * 0.6
        )

    elif position.input_level > 0.8 and position.dynamic_range < 0.45:
        # LOUD + COMPRESSED (crest < ~13 dB) → EXPAND DYNAMICS (de-mastering)
        # Loudness war casualties - restore natural dynamics
        # Examples: Pantera (DR 0.35, crest 11.30), Motörhead (DR 0.37, crest 11.57), Soda Stereo (DR 0.73, crest 15.14)
        # Blend: Favor content rule (80%) for safety
        content_recommended = -17.0  # Reduce RMS to create headroom
        params.output_target_rms = (
            content_recommended * 0.8 +
            preset_target_lufs * 0.2
        )
        params.compression_amount = 0.0  # NO compression
        params.expansion_amount = 0.7  # EXPAND dynamics (higher = more expansion)
        params.dynamics_intensity = 0.0
        print(f"[Content Rule] LOUD+COMPRESSED (Level:{position.input_level:.2f}, DR:{position.dynamic_range:.2f}) → EXPAND dynamics, blended RMS {params.output_target_rms:.1f} dB")

    elif position.input_level > 0.85 and position.dynamic_range >= 0.45 and position.dynamic_range < 0.6:
        # VERY LOUD + MODERATE DYNAMICS → LIGHT COMPRESSION
        # Examples: Testament (Level 0.88, DR 0.52, crest 12.55)
        # Already loud but could be tighter
        content_recommended = -15.0  # More conservative boost to match Matchering
        params.output_target_rms = (
            content_recommended * 0.3 +
            preset_target_lufs * 0.7
        )
        params.compression_amount = 0.42  # Light compression
        params.expansion_amount = 0.0  # NO expansion
        print(f"[Content Rule] VERY LOUD+MODERATE DYNAMICS (Level:{position.input_level:.2f}, DR:{position.dynamic_range:.2f}) → Light compression, blended RMS {params.output_target_rms:.1f} dB")

    elif position.input_level > 0.7 and position.input_level <= 0.85 and position.dynamic_range >= 0.6 and position.dynamic_range < 0.8:
        # MODERATELY LOUD + HIGH DYNAMICS → LIGHT EXPANSION
        # Examples: Soda Stereo (Level 0.76, DR 0.73, crest 15.14)
        # These have good dynamics that should be preserved/enhanced
        content_recommended = -14.0  # Slight RMS reduction
        params.output_target_rms = (
            content_recommended * 0.6 +
            preset_target_lufs * 0.4
        )
        params.compression_amount = 0.0  # NO compression
        params.expansion_amount = 0.4  # Light expansion
        print(f"[Content Rule] MODERATELY LOUD+HIGH DYNAMICS (Level:{position.input_level:.2f}, DR:{position.dynamic_range:.2f}) → Light expansion, blended RMS {params.output_target_rms:.1f} dB")

    elif position.input_level > 0.8 and position.dynamic_range >= 0.6:
        # LOUD + VERY GOOD DYNAMICS (crest > ~15 dB) → Preserve excellent balance
        content_recommended = -15.0  # More conservative target to match Matchering
        params.output_target_rms = (
            content_recommended * 0.3 +
            preset_target_lufs * 0.7
        )
        print(f"[Content Rule] LOUD+VERY DYNAMIC (Level:{position.input_level:.2f}, DR:{position.dynamic_range:.2f}) → Blended RMS {params.output_target_rms:.1f} dB")

    elif position.input_level > 0.7 and position.dynamic_range > 0.4:
        # Loud + some dynamics (like live recordings) - bring up RMS
        # Blend content recommendation with user preset (30/70 to match Matchering)
        content_recommended = -15.0  # More conservative
        params.output_target_rms = (
            content_recommended * 0.3 +
            preset_target_lufs * 0.7
        )
        print(f"[Content Rule] Loud+Dynamic detected (Level:{position.input_level:.2f}, DR:{position.dynamic_range:.2f}) → Blended target RMS {params.output_target_rms:.1f} dB (content:{content_recommended:.1f}, preset:{preset_target_lufs:.1f})")

    elif position.input_level > 0.6 and position.dynamic_range > 0.5:
        # Moderately loud + dynamic - still needs some boost
        content_recommended = -13.0
        params.output_target_rms = (
            content_recommended * 0.5 +
            preset_target_lufs * 0.5
        )

    elif position.input_level < 0.3:
        # Very quiet - significant boost needed
        content_recommended = -14.0
        params.output_target_rms = (
            content_recommended * 0.5 +
            preset_target_lufs * 0.5
        )

    return params
