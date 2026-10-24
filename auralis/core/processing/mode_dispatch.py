"""
Mode Dispatch
~~~~~~~~~~~~~

HybridProcessor's three mode bodies (reference / adaptive / hybrid), split
out in #6272 beside the mode processors they delegate to. Each takes the
processor as its first argument (the #4245 coordinator pattern); the class
methods stay thin delegators so `patch.object` and the lock discipline in
HybridProcessor.process() are unchanged.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import TYPE_CHECKING

import numpy as np

from ...utils.audio_validation import validate_audio_finite

if TYPE_CHECKING:
    from auralis.core.hybrid_processor import HybridProcessor

from ..hybrid_stage_dispatch import (
    process_reference_mode as _reference_stage_dispatch,
)
from ...utils.logging import info

__all__ = ["process_reference_mode", "process_adaptive_mode", "process_hybrid_mode"]


def process_reference_mode(processor: "HybridProcessor", target_audio: np.ndarray,
                           reference: np.ndarray) -> np.ndarray:
    """Process using traditional reference-based matching. See
    hybrid_stage_dispatch.process_reference_mode() (#5463)."""
    return _reference_stage_dispatch(processor, target_audio, reference)

def process_adaptive_mode(
    processor: "HybridProcessor", target_audio: np.ndarray
) -> np.ndarray:
    """
    Process using adaptive mastering without reference.

    Uses the internal processor logic directly: hybrid_processor is the
    actual processor called by AudioProcessingPipeline.
    """
    info("Processing in adaptive mode")

    info("Using continuous parameter space (fingerprint-based)")

    # Use fixed targets if set (from .25d file); this bypasses expensive
    # fingerprint extraction on every chunk
    fixed_params = processor.current_targets if processor.current_targets is not None else None

    # Delegate to continuous mode processor
    processed = processor.continuous_mode.process(target_audio, processor.eq_processor,
                                            fixed_params=fixed_params)

    # Store fingerprint and parameters for debugging
    processor.last_content_profile = {
        'fingerprint': processor.continuous_mode.last_fingerprint,
        'coordinates': processor.continuous_mode.last_coordinates,
        'parameters': processor.continuous_mode.last_parameters,
    }

    # Apply brick-wall limiter for final peak control
    # Ensures output never clips and stays within safe range
    processed = processor.brick_wall_limiter.process(processed)
    # Sample-count invariant: limiter must preserve length (fixes #2519).
    # raise, not assert — asserts vanish under python -O (#5533, cf. #5511).
    if processed.shape != target_audio.shape:
        raise RuntimeError(
            f"Sample count mismatch after limiter (adaptive): "
            f"expected {target_audio.shape}, got {processed.shape}"
        )

    # Fail fast on NaN/Inf in mastering output — surface DSP bugs rather than
    # silently masking them with zero-replacement (fixes #2520).
    processed = validate_audio_finite(processed, context="adaptive mode output", repair=False)

    return processed

def process_hybrid_mode(
    processor: "HybridProcessor", target_audio: np.ndarray, reference: np.ndarray | None
) -> np.ndarray:
    """Process using hybrid approach combining reference and adaptive"""
    info("Processing in hybrid mode")

    # Reference, if provided, is a pre-loaded NumPy array (#4035).
    reference_audio = reference

    # Delegate to hybrid mode processor
    processed = processor.hybrid_mode.process(target_audio, reference_audio, processor.eq_processor)

    # Apply brick-wall limiter for final peak control
    # Ensures output never clips and stays within safe range
    processed = processor.brick_wall_limiter.process(processed)
    # Sample-count invariant: limiter must preserve length (fixes #2519).
    # raise, not assert — asserts vanish under python -O (#5533, cf. #5511).
    if processed.shape != target_audio.shape:
        raise RuntimeError(
            f"Sample count mismatch after limiter (hybrid): "
            f"expected {target_audio.shape}, got {processed.shape}"
        )

    # Fail fast on NaN/Inf in mastering output — surface DSP bugs rather than
    # silently masking them with zero-replacement (fixes #2520).
    processed = validate_audio_finite(processed, context="hybrid mode output", repair=False)

    return processed
