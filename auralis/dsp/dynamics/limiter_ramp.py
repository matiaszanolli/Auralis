"""
Limiter attack ramp
~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Turns the stepped sliding-minimum gain of ``BrickWallLimiter`` into a linear
attack ramp (#5699).
"""

import numpy as np
from scipy.ndimage import minimum_filter1d, uniform_filter1d


def ramp_gain_reduction(
    target_gains: np.ndarray,
    sample_peaks: np.ndarray,
    lookahead: int,
    threshold_linear: float,
) -> np.ndarray:
    """
    Ramp the gain reduction in over ``lookahead`` samples.

    ``target_gains[j]`` already caps every sample in ``[j, j + lookahead)``, so
    a trailing mean over ``[i - lookahead + 1, i]`` is a mean of values that
    each cap sample ``i`` and therefore still caps it, while a peak at ``p``
    pulls the mean down by ``(1 - t) / lookahead`` per sample from
    ``p - lookahead + 1`` until it reaches ``t`` exactly at ``p``.

    The front edge is replicated, so a block never relies on gain reduction it
    was not given: a peak inside the first ``lookahead`` samples of a call is
    still capped, at the price of a step there (the limiter has no latency to
    look into the next call).

    Windows containing no limiting are snapped back to exactly 1.0 so the
    vectorised unity-run release in ``BrickWallLimiter._release_envelope``
    (#3751) is not defeated by running-sum rounding, and the result is clipped
    to each sample's own cap so rounding can never lift a peak over the ceiling.

    Args:
        target_gains: Sliding-minimum gain per sample, in (0, 1].
        sample_peaks: Per-sample max |audio| across channels, same length.
        lookahead: Look-ahead window in samples.
        threshold_linear: Ceiling in linear scale.

    Returns:
        Gains in (0, 1]; ``target_gains`` unchanged when ``lookahead < 2``.
    """
    if lookahead < 2:
        return target_gains
    # Trailing window [i - lookahead + 1, i]; a positive origin looks at
    # earlier samples.
    origin = (lookahead - 1) // 2
    gains = target_gains.astype(np.float64)
    ramped = uniform_filter1d(gains, size=lookahead, mode='nearest', origin=origin)
    no_limiting = minimum_filter1d(
        gains, size=lookahead, mode='nearest', origin=origin
    ) >= 1.0
    ramped[no_limiting] = 1.0
    cap = threshold_linear / np.maximum(sample_peaks, 1e-10)
    result: np.ndarray = np.minimum(ramped, np.minimum(cap, 1.0))
    return result
