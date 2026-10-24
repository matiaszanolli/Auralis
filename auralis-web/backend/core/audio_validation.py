#!/usr/bin/env python3

"""
Audio Input Validation
~~~~~~~~~~~~~~~~~~~~~~

``validate_audio`` split out of ``AudioProcessingPipeline`` (#6270): input
normalisation (empty/silence handling, mono->stereo, minimum length,
NaN/Inf detection) is a precondition of the pipeline, not orchestration.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)
from auralis.core.hybrid_stage_dispatch import MIN_SAMPLES


def validate_audio(audio: np.ndarray, allow_empty: bool = False) -> np.ndarray:
    """
    Validate and normalize audio array.

    Consolidates validation from hybrid_processor.process() with best practices:
    - Empty array handling
    - Silence detection (all zeros)
    - Mono to stereo conversion
    - Minimum sample count check
    - NaN/infinite value detection

    Args:
        audio: Input audio array
        allow_empty: If True, allow empty arrays (return as-is)

    Returns:
        Validated and normalized audio array. Audio shorter than
        MIN_SAMPLES is returned unprocessed rather than rejected —
        the same policy as the engine's
        `hybrid_stage_dispatch.validate_and_normalize_input()` (#6194):
        the raise broke the pipeline's `len(output) == len(input)`
        invariant for short buffers, and the Rust FFT panics the guard
        originally defended against are fixed at the source (#4520).

    Raises:
        ValueError: If audio is invalid
    """
    # Validate type
    if not isinstance(audio, np.ndarray):
        raise ValueError(f"Audio must be NumPy array, got {type(audio)}")

    # Handle empty audio
    if len(audio) == 0:
        if allow_empty:
            logger.debug("Empty audio array (allowed)")
            return audio
        else:
            raise ValueError("Audio array is empty")

    # Handle silence (all zeros) - return as-is to avoid NaN in downstream processing
    if np.allclose(audio, 0.0, atol=1e-10):
        logger.debug("Audio is silence (all zeros), returning as-is")
        return audio.copy()

    # Convert mono to stereo if needed
    if audio.ndim == 1:
        audio = np.column_stack([audio, audio])
        logger.debug(f"Converted mono to stereo: shape now {audio.shape}")

    # Check for minimum sample count — return unprocessed, mirroring the
    # engine's short-buffer policy (#6194); see the docstring.
    if audio.shape[0] < MIN_SAMPLES:
        logger.warning(
            f"Audio too short to master ({audio.shape[0]} samples, "
            f"need {MIN_SAMPLES}); returning it unprocessed"
        )
        return audio

    # Check for NaN or infinite values
    if not np.all(np.isfinite(audio)):
        num_nan = np.sum(np.isnan(audio))
        num_inf = np.sum(np.isinf(audio))
        raise ValueError(
            f"Audio contains invalid values: {num_nan} NaN, {num_inf} infinite"
        )

    logger.debug(f"Audio validated: shape={audio.shape}, dtype={audio.dtype}")
    return audio


def finite_or_fallback(
    processed: np.ndarray, audio: np.ndarray, chunk_index: int | None
) -> np.ndarray:
    """Guard the pipeline boundary against non-finite DSP output (#4672).

    np.clip does NOT sanitize NaN (np.clip(nan, -1, 1) is still nan), so an
    unguarded NaN here reaches encode_to_wav's PCM_16 write as an undefined
    sample AND poisons LevelManager.calculate_rms -> rms_history for every
    subsequent chunk in the track (np.sqrt(np.mean(audio**2)) on a NaN input
    is NaN, and nan comparisons are always False, so smoothing silently stops
    applying instead of erroring). Falling back to the unprocessed audio
    (same shape/dtype the caller already validated as finite) produces one
    audible discontinuity instead of a silent, permanent poisoning — loud and
    diagnosable rather than a click nobody can trace back to its chunk.

    Returns ``audio`` itself (identity checkable by the caller) when the
    processed output is not finite.
    """
    if np.all(np.isfinite(processed)):
        return processed
    num_nan = int(np.sum(np.isnan(processed)))
    num_inf = int(np.sum(np.isinf(processed)))
    logger.warning(
        f"Processor produced non-finite output (chunk_index={chunk_index}): "
        f"{num_nan} NaN, {num_inf} infinite — falling back to unprocessed audio"
    )
    return audio
