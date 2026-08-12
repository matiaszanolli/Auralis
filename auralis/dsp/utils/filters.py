# -*- coding: utf-8 -*-

"""
Zero-Phase Filter Helpers
~~~~~~~~~~~~~~~~~~~~~~~~~

`sosfiltfilt` filters forward and backward, so it pads the signal at both ends
before filtering. SciPy requires the signal to be **longer than that pad**, and
raises otherwise:

    ValueError: The length of the input vector x must be greater than padlen,
    which is 15.

For an order-2 Butterworth bandpass (2 second-order sections) that means any
buffer of 15 samples or fewer is rejected — a hard crash mid-DSP, not a
degraded result. No caller in this codebase checked for it (#4520): the audio
engine happened to be shielded by a blanket "reject anything under 1024
samples" guard in HybridProcessor, so the gap only surfaced when that guard was
relaxed to preserve sample count.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import sosfiltfilt

from ...utils.logging import debug

__all__ = ["sosfiltfilt_padlen", "is_long_enough_for_sosfiltfilt", "sosfiltfilt_safe"]


def sosfiltfilt_padlen(sos: np.ndarray) -> int:
    """SciPy's default `padlen` for `sosfiltfilt` with this filter.

    Mirrors scipy's own default — `3 * (2 * n_sections + 1)` — verified
    against scipy by measurement, not read off the docs: for 1/2/4 sections the
    shortest accepted signal is 10/16/28 samples respectively, i.e. `padlen + 1`.
    """
    n_sections = int(np.asarray(sos).shape[0])
    return 3 * (2 * n_sections + 1)


def is_long_enough_for_sosfiltfilt(sos: np.ndarray, n_samples: int) -> bool:
    """Whether `sosfiltfilt` will accept a signal of `n_samples`.

    The comparison is strictly greater-than, matching scipy: a signal of exactly
    `padlen` samples is still rejected.
    """
    return n_samples > sosfiltfilt_padlen(sos)


def sosfiltfilt_safe(
    sos: np.ndarray,
    audio: np.ndarray,
    axis: int = 0,
    context: str = "filter",
    on_too_short: str = "passthrough",
) -> np.ndarray:
    """`sosfiltfilt` that degrades gracefully instead of raising.

    Applies the filter when the signal is long enough; otherwise falls back per
    `on_too_short`, preserving the sample-count invariant the audio pipeline
    depends on for gapless playback.

    Always returns the input dtype. `sosfiltfilt` promotes to float64
    internally, so an unguarded call silently upcasts a float32 signal and any
    later `audio + filtered` add inherits the promotion (#3468 / #4105) — the
    cast keeps this wrapper consistent with the hand-written
    `np.asarray(sosfiltfilt(...), dtype=...)` calls it replaces.

    Args:
        sos: Second-order-sections filter, as returned by `butter(..., output='sos')`.
        audio: Signal to filter.
        axis: Axis to filter along (0 for (samples, channels) audio).
        context: Name used in the debug log when the filter is skipped.
        on_too_short: Fallback when the signal is shorter than `padlen`. Pick by
            what the filter's OUTPUT means to the caller — the two are not
            interchangeable:

            - ``"passthrough"`` — return the signal unchanged. Correct when the
              filter shapes the signal in place, so skipping it means "no
              shaping applied".
            - ``"zeros"`` — return silence. Correct for **band extraction**,
              where the result is one band's content: a band that could not be
              extracted holds no energy. Returning the full-band signal instead
              would claim every band contains the entire signal, so a caller
              summing per-band contributions would apply each one at full
              strength (this is exactly what made short audio come back
              *triple*-widened from ``adjust_stereo_width_multiband``, #4520).

    Returns:
        The filtered signal, or the chosen fallback when it is too short.

    Raises:
        ValueError: If `on_too_short` is not one of the two accepted values.
    """
    if on_too_short not in ("passthrough", "zeros"):
        raise ValueError(
            f"on_too_short must be 'passthrough' or 'zeros', got {on_too_short!r}"
        )

    if not is_long_enough_for_sosfiltfilt(sos, audio.shape[axis]):
        debug(
            f"[{context}] Skipping zero-phase filter ({on_too_short}): "
            f"{audio.shape[axis]} samples is not more than "
            f"padlen {sosfiltfilt_padlen(sos)}"
        )
        return np.zeros_like(audio) if on_too_short == "zeros" else audio.copy()

    return np.asarray(sosfiltfilt(sos, audio, axis=axis), dtype=audio.dtype)
