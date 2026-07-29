"""Shared high-frequency lift response.

The exciter, clarity, presence, and air stages overlap. Their shared multiplier
is derived from the same corpus-calibrated spectral coordinate used by the
continuous mastering space. A Gaussian response gives the most lift to sources
that are moderately low on that axis, while smoothly reducing intervention at
both extremes: near-empty HF has little musical foundation to amplify, and
already-bright material needs little additional energy.
"""

from __future__ import annotations

import math

HF_NEED_CENTER = 0.35
"""Spectral coordinate receiving the strongest shared HF response."""

HF_NEED_WIDTH = 0.25
"""Standard deviation of the smooth response across the spectral axis."""


def hf_lift_factor(spectral_balance: float) -> float:
    """Return the smooth shared HF multiplier for a spectral coordinate.

    ``spectral_balance`` is already calibrated from the deterministic 508-track
    corpus sample. No raw fingerprint value is compared with an arbitrary
    ``0..1`` fullness threshold.
    """
    distance = (float(spectral_balance) - HF_NEED_CENTER) / HF_NEED_WIDTH
    return math.exp(-0.5 * distance * distance)
