"""Shared high-frequency lift budget.

The four high-frequency enhancement stages — harmonic exciter, clarity boost,
presence enhancement, and air enhancement — run sequentially over overlapping
bands (1.5 kHz … 20 kHz). Each one historically scaled its boost *inversely*
to how much energy already lived in its band (``factor = 1 - ramp(content)``),
so a dark, bandwidth-limited source triggered **all four near maximum at the
same time** with no shared ceiling. On a band that is essentially empty, the
added energy is enormous in *relative* terms — the result is fizz/harshness
rather than musical air (measured +6 dB relative presence lift on dark material).

This module supplies a single multiplier that every HF stage applies to its
computed boost, enforcing a shared budget:

* **Moderately dull** sources (some HF present, just under-represented) get the
  full lift — this is exactly where brightening sounds musical.
* **HF-dead** sources (presence + air ≈ 0) get a reduced lift toward a floor —
  there is no foundation to lift, so a large boost only amplifies noise and
  exciter fizz. The harmonic exciter still generates *new* content for these,
  but the shelves above it stay restrained.

This replaces unbounded per-stage stacking with one coordinated ceiling.
"""

from __future__ import annotations


# HF foundation (presence_pct + air_pct) at/above which full lift is allowed.
# Below this the source is treated as HF-dead and lift is tapered to the floor.
HF_SWEET_SPOT = 0.04

# Minimum fraction of the nominal lift applied to a completely HF-dead source.
# Keeps some brightening for dark material without amplifying near-silence to fizz.
HF_DEAD_FLOOR = 0.3


def hf_lift_factor(presence_pct: float, air_pct: float) -> float:
    """Shared multiplier (0..1) for every HF enhancement stage's boost.

    Args:
        presence_pct: Fingerprint presence percentage (4-6 kHz region, 0-1).
        air_pct: Fingerprint air percentage (6-20 kHz region, 0-1).

    Returns:
        Multiplier in ``[HF_DEAD_FLOOR, 1.0]``. ``1.0`` for sources with a real
        HF foundation; tapering to ``HF_DEAD_FLOOR`` as that foundation vanishes.
    """
    hf = max(0.0, presence_pct) + max(0.0, air_pct)
    if hf >= HF_SWEET_SPOT:
        return 1.0
    return HF_DEAD_FLOOR + (1.0 - HF_DEAD_FLOOR) * (hf / HF_SWEET_SPOT)
