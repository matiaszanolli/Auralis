"""
Audio Validation Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~

Utilities for validating audio data integrity (NaN, Inf detection)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from .logging import Code, ModuleError, warning


def validate_audio_finite(
    audio: np.ndarray,
    context: str = "audio",
    repair: bool = False
) -> np.ndarray:
    """
    Validate that audio contains only finite values (no NaN or Inf).

    Args:
        audio: Audio array to validate
        context: Description of where this audio came from (for error messages)
        repair: If True, replace NaN/Inf with silence and warn. If False, raise error.

    Returns:
        Validated (and possibly repaired) audio array

    Raises:
        ModuleError: If NaN/Inf detected and repair=False
    """
    # Check for NaN or Inf
    has_nan = np.any(np.isnan(audio))
    has_inf = np.any(np.isinf(audio))

    if not (has_nan or has_inf):
        return audio  # All good

    # Count problematic samples for reporting
    nan_count = np.sum(np.isnan(audio))
    inf_count = np.sum(np.isinf(audio))
    total_samples = audio.size
    affected_pct = ((nan_count + inf_count) / total_samples) * 100

    error_msg = (
        f"{Code.ERROR_NAN_DETECTED} in {context}: "
        f"{nan_count} NaN, {inf_count} Inf ({affected_pct:.2f}% of samples)"
    )

    if repair:
        # Replace NaN/Inf with silence (zero)
        repaired = audio.copy()
        repaired[~np.isfinite(repaired)] = 0.0

        warning(
            f"{Code.WARNING_NAN_DETECTED} in {context}: "
            f"Replaced {nan_count} NaN and {inf_count} Inf values with silence "
            f"({affected_pct:.2f}% of samples)"
        )

        return repaired
    else:
        # Fail fast
        raise ModuleError(error_msg)


def check_audio_finite(audio: np.ndarray) -> bool:
    """
    Check if audio contains only finite values (no NaN or Inf).

    Args:
        audio: Audio array to check

    Returns:
        True if all values are finite, False otherwise
    """
    return bool(np.all(np.isfinite(audio)))


def sanitize_audio(audio: np.ndarray, context: str = "audio") -> np.ndarray:
    """
    Sanitize audio by replacing NaN/Inf with silence (zero).

    This is a convenience function that always repairs NaN/Inf values
    and logs a warning. Use this for production resilience.

    Args:
        audio: Audio array to sanitize
        context: Description of where this audio came from

    Returns:
        Sanitized audio array with NaN/Inf replaced by zeros
    """
    return validate_audio_finite(audio, context=context, repair=True)
