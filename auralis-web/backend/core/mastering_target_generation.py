"""
Mastering-target derivation from a 25D fingerprint (split from
mastering_target_service.py, #5833). Pure functions of the fingerprint.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from auralis.dsp.constants import CORPUS_BAND_CENTERS
from auralis.dsp.utils.loudness_targets import DEFAULT_TARGET_LUFS, STREAMING_TARGET_LUFS

# The corpus medians are the calibration, not hand-set "ideal" shares
# (#5695): the previous table (sub 0.05, bass 0.15, low-mid 0.18, mid 0.22,
# upper-mid 0.20, presence 0.13, air 0.07) described nothing the fingerprint
# band fractions look like (energy falls steeply with frequency), so a
# corpus-MEDIAN track still got bass clamped at -6 dB, upper-mid +6 and a
# +9.5 dB summed high shelf — a content-independent bass-cut/treble-boost
# tilt on every fixed-target render. Shared with the per-chunk fingerprint
# EQ path (parameter_generator_eq.py) via dsp/constants, so the two cannot
# drift again.
_IDEAL_BAND_SHARE = CORPUS_BAND_CENTERS


def generate_targets_from_fingerprint(fingerprint: Any) -> dict[str, Any]:
    """
    Generate mastering targets from 25D fingerprint.

    Consolidates logic from chunked_processor._generate_targets_from_fingerprint().

    This converts acoustic characteristics into processing parameters.
    Targets remain fixed for the entire track, enabling fast processing.

    Args:
        fingerprint: MasteringFingerprint instance or dict

    Returns:
        Dictionary of mastering targets
    """
    # Handle both dict and MasteringFingerprint objects
    if hasattr(fingerprint, '__dict__'):
        fp_dict = fingerprint.__dict__
    else:
        fp_dict = fingerprint

    # Get frequency and dynamics data
    freq = fp_dict.get('frequency', {})
    dynamics = fp_dict.get('dynamics', {})

    # Target loudness: nudge toward streaming standard (-14 LUFS) while
    # preserving the track's original loudness character (fixes #2726).
    current_lufs = fp_dict.get('lufs', dynamics.get('lufs', DEFAULT_TARGET_LUFS))
    streaming_target = STREAMING_TARGET_LUFS
    # Blend 60% toward streaming target, 40% original character
    target_lufs = current_lufs * 0.4 + streaming_target * 0.6

    # Target crest factor (preserve dynamic range character)
    current_crest = fp_dict.get('crest_db', dynamics.get('crest_db', 12.0))
    target_crest = max(10.0, current_crest * 0.85)  # Slight reduction

    # EQ adjustments based on frequency balance. A band missing from the
    # fingerprint falls back to its own ideal share (so it gets no adjustment).
    eq_adjustments = {
        band: calculate_eq_adjustment(
            fp_dict.get(f'{band}_pct', freq.get(f'{band}_pct', ideal)), ideal=ideal
        )
        for band, ideal in _IDEAL_BAND_SHARE.items()
    }

    return {
        'target_lufs': target_lufs,
        # Track-level source loudness (fingerprint scale). Final
        # normalisation applies the single gain target_lufs - source_lufs
        # to every chunk, so quiet and loud sections keep their relative
        # level (#5552).
        'source_lufs': current_lufs,
        'target_crest_db': target_crest,
        'eq_adjustments_db': eq_adjustments,
        'compression': {
            'ratio': 2.5,
            'amount': 0.6
        }
    }


def calculate_eq_adjustment(current_fraction: float, ideal: float) -> float:
    """
    Calculate EQ adjustment in dB to reach the ideal band share.

    Consolidates logic from chunked_processor._calculate_eq_adjustment().

    Args:
        current_fraction: Current band energy as a FRACTION of the total
            (0-1; the fingerprint's ``*_pct`` fields are fractions, not
            percentages).
        ideal: Ideal band energy fraction, same units.

    Returns:
        EQ adjustment in dB (clamped to ±6 dB)
    """
    # Simple proportional adjustment
    diff = ideal - current_fraction
    # ±1 percentage point (0.01) difference = ±0.5 dB adjustment (gentle).
    # This used to take diff*0.5 directly on 0-1 fractions, which treated
    # them as percentages: any band 0.12 off its ideal saturated the ±6 dB
    # clamp, so every track got the same near-maximal tilt (#5554).
    adjustment = diff * 100.0 * 0.5
    # Clamp to reasonable range
    return max(-6.0, min(6.0, adjustment))
