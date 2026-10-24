"""
Audio Validation Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~

Utilities for validating audio data integrity (NaN, Inf detection)

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

from .logging import Code, ModuleError, error, warning

#: Fraction of non-finite samples up to which an in-stage ``repair=True``
#: call may still zero them (#6105). Above it the buffer is not "a few stray
#: samples" but the output of a broken stage: zeroing it would ship a silent
#: chunk and pre-empt the fail-fast guards and the pipeline's
#: unprocessed-audio fallback, so :func:`validate_audio_finite` raises
#: instead. Last-boundary writers (saver, realtime output) repair
#: unconditionally and do not pass a limit.
MAX_IN_STAGE_REPAIR_FRACTION = 0.001


def validate_audio_finite(
    audio: np.ndarray,
    context: str = "audio",
    repair: bool = False,
    repair_max_fraction: float | None = None,
) -> np.ndarray:
    """
    Validate that audio contains only finite values (no NaN or Inf).

    Args:
        audio: Audio array to validate
        context: Description of where this audio came from (for error messages)
        repair: If True, replace NaN/Inf with silence and warn. If False, raise error.
        repair_max_fraction: With ``repair=True``, refuse the repair (raise)
            when more than this fraction of samples is non-finite (#6105).
            ``None`` repairs unconditionally — only appropriate at a final
            output boundary where the alternative is emitting the NaNs.

    Returns:
        Validated (and possibly repaired) audio array

    Raises:
        ModuleError: If NaN/Inf detected and repair=False, or the non-finite
            fraction exceeds ``repair_max_fraction``
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
        if (
            repair_max_fraction is not None
            and (nan_count + inf_count) / total_samples > repair_max_fraction
        ):
            # Too much of the buffer is non-finite to pass off as stray
            # samples. Raise so the boundary fail-fast guards and the
            # pipeline's unprocessed-audio fallback can fire (#6105).
            error(
                f"{error_msg} — non-finite fraction exceeds the in-stage "
                f"repair limit ({repair_max_fraction:.3%}); refusing to "
                f"zero the buffer"
            )
            raise ModuleError(error_msg)

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
