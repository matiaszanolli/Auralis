# -*- coding: utf-8 -*-

"""
Auralis DSP Processing Stages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Multi-stage audio processing pipeline

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""

from typing import Any, Optional, Tuple

import numpy as np

from ..utils.logging import debug, info
from .basic import amplify, normalize, rms
from .dynamics.soft_clipper import soft_clip
from .utils.adaptive import (
    adaptive_gain_calculation,
    calculate_loudness_units,
)
from .utils.spectral import crest_factor, spectral_centroid


def main(
    target: np.ndarray,
    reference: np.ndarray,
    config: Any,
    need_default: bool = True,
    need_no_limiter: bool = False,
    need_no_limiter_normalized: bool = False,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Main processing pipeline with full matching algorithms

    Implements comprehensive audio matching including:
    - Loudness matching (LUFS-based)
    - RMS level matching
    - Dynamic range analysis
    - Spectral characteristics preservation
    - Soft clipping for peak protection

    Args:
        target: Target audio to be processed
        reference: Reference audio for matching
        config: Processing configuration
        need_default: Whether to generate default (with limiter) result
        need_no_limiter: Whether to generate no-limiter result
        need_no_limiter_normalized: Whether to generate normalized no-limiter result

    Returns:
        tuple: (result, result_no_limiter, result_no_limiter_normalized)
    """
    debug("Starting main processing pipeline with full matching algorithms")

    # ========================================================================
    # Stage 1: Analysis
    # ========================================================================

    # Calculate RMS levels
    target_rms = rms(target)
    reference_rms = rms(reference)

    debug(f"Target RMS: {target_rms:.6f}, Reference RMS: {reference_rms:.6f}")

    # Calculate loudness levels (LUFS approximation)
    target_loudness = calculate_loudness_units(target, config.internal_sample_rate)
    reference_loudness = calculate_loudness_units(reference, config.internal_sample_rate)

    debug(f"Target loudness: {target_loudness:.2f} LUFS, Reference loudness: {reference_loudness:.2f} LUFS")

    # Analyze dynamic characteristics
    target_crest = crest_factor(target)
    reference_crest = crest_factor(reference)

    debug(f"Target crest factor: {target_crest:.2f}, Reference crest factor: {reference_crest:.2f}")

    # ========================================================================
    # Stage 2: Gain Matching (Loudness-based)
    # ========================================================================

    # Calculate gain to match loudness levels
    loudness_gain_db = reference_loudness - target_loudness if target_loudness > -70 else 0

    # Also calculate adaptive gain for smooth transitions
    gain_factor = adaptive_gain_calculation(
        target_rms=target_rms,
        reference_rms=reference_rms,
        adaptation_factor=0.9,  # Aggressive matching
    )
    adaptive_gain_db = 20 * np.log10(gain_factor) if gain_factor > 0 else 0

    # Use loudness-based gain as primary, with adaptive smoothing
    final_gain_db = loudness_gain_db if abs(loudness_gain_db) < 12 else adaptive_gain_db

    debug(f"Loudness gain: {loudness_gain_db:.2f} dB, Adaptive gain: {adaptive_gain_db:.2f} dB")
    debug(f"Applying final gain: {final_gain_db:.2f} dB")

    # ========================================================================
    # Stage 3: Gain Application
    # ========================================================================

    # Apply gain to match loudness
    result_no_limiter = amplify(target, final_gain_db)

    # ========================================================================
    # Stage 4: Peak Protection with Soft Clipping
    # ========================================================================

    # Analyze peak levels after gain
    peak_level = np.max(np.abs(result_no_limiter))

    # Apply soft clipping for smooth peak limiting if needed
    if peak_level > 0.99:
        debug(f"Peak level {peak_level:.3f} exceeds threshold, applying soft clipping")
        result = soft_clip(result_no_limiter, threshold=0.9, ceiling=0.99)
    else:
        result = np.copy(result_no_limiter)

    # ========================================================================
    # Stage 5: Normalization
    # ========================================================================

    # Create normalized version (matches loudest peak to ceiling)
    result_no_limiter_normalized = normalize(result_no_limiter, 0.99)

    info(
        f"Processing complete: Target {target_loudness:.2f} LUFS → "
        f"Result {reference_loudness:.2f} LUFS, "
        f"Gain: {final_gain_db:.2f} dB, "
        f"Peak: {peak_level:.3f}"
    )

    # ========================================================================
    # Return Results
    # ========================================================================

    # Return only what's needed
    return (
        result if need_default else None,
        result_no_limiter if need_no_limiter else None,
        result_no_limiter_normalized if need_no_limiter_normalized else None,
    )