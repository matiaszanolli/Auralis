"""
Delta-from-Target EQ Curve Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Turn (source_fingerprint, target_fingerprint) into a 5-shelf EQ curve. The
target comes from the soft k-NN reference cloud (target_derivation.py); this
module handles the band-arithmetic that converts "we want band X to look
like Y" into actual EQ gains.

Key properties:
  * SYMMETRIC — if the source's band is louder than the target, we CUT
    (negative gain). Old deficit-based math could only boost, which is what
    drove the "Iron Maiden HF overdrive" complaint.
  * ASYMMETRIC CAPS per band — gentler bounds on HF lifts (where
    perceived harshness lives), freer HF cuts; freer LF lifts (preserve
    warmth), modest LF cuts. See `BAND_CAPS_DB`.
  * SMOOTH SATURATION via tanh — no abrupt jumps when source and target
    diverge sharply. The cap is the hard limit, tanh shapes the approach.
  * EPSILON-PROTECTED — log of tiny fractions (air_pct = 0.001) doesn't
    explode.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping


# ---------------------------------------------------------------------------
# Per-band asymmetric caps (dB). Picked from perceptual considerations,
# not genre — these are properties of human hearing.
#
#   K_lift = maximum boost we'd ever apply to this band
#   K_cut  = maximum cut  we'd ever apply
#
# Rationale:
#   sub_bass/bass: aggressive lift (perceived warmth), gentle cut
#   low_mid/mid:   moderate symmetric (the body of the mix)
#   upper_mid:     gentle lift, moderate cut (harshness band)
#   presence:      gentle lift, AGGRESSIVE cut (sibilance / harshness)
#   air:           moderate symmetric (mostly euphonic)
# ---------------------------------------------------------------------------

BAND_CAPS_DB: dict[str, tuple[float, float]] = {
    'sub_bass_pct':   (4.0, 2.0),
    'bass_pct':       (4.0, 2.0),
    'low_mid_pct':    (2.0, 2.0),
    'mid_pct':        (2.0, 2.0),
    'upper_mid_pct':  (1.5, 2.5),
    'presence_pct':   (1.5, 3.0),
    'air_pct':        (2.0, 2.0),
}


# Floor applied before log10 to keep tiny fractions from producing huge
# negative dB values. 1e-4 = -40 dB worth of energy — well below the
# threshold at which a band is acoustically meaningful.
_FRACTION_FLOOR = 1e-4

# Bands whose source fraction is below this threshold are treated as
# acoustically empty — we don't try to "boost silence". The delta is set
# to zero regardless of what the target says. Prevents the saturation
# artifact where source=0.000 in a band makes log(target/floor) blow up.
_EMPTY_BAND_THRESHOLD = 0.005      # 0.5% of energy


@dataclass(frozen=True)
class DeltaEQResult:
    """The 5-shelf EQ curve plus per-band diagnostics."""

    # 5-shelf EQ curve (matches existing ProcessingParameters.eq_curve schema)
    low_shelf_gain: float
    low_mid_gain: float
    mid_gain: float
    high_mid_gain: float
    high_shelf_gain: float

    # Diagnostics: the raw per-band delta (post-cap) for debugging/UI.
    per_band_delta_db: Mapping[str, float]


def compute_delta_eq(
    source: Mapping[str, float],
    target: Mapping[str, float],
) -> DeltaEQResult:
    """Produce a 5-shelf EQ curve that pulls source toward target.

    Each band's gain is `K * tanh(delta_db / K)` where `delta_db = 10 *
    log10(target/source)` and `K` is the asymmetric per-band cap. The
    smooth saturation means small deltas pass through nearly linearly while
    large ones approach the cap asymptotically (no clipping discontinuity).

    Args:
        source: Source band fractions (must contain BAND_CAPS_DB keys).
        target: Target band fractions (typically from derive_target).

    Returns:
        DeltaEQResult with the 5-shelf curve + per-band raw deltas.
    """
    per_band: dict[str, float] = {}
    for band, (k_lift, k_cut) in BAND_CAPS_DB.items():
        src_val_raw = float(source.get(band, 0.0))
        # Acoustically empty bands get no correction — boosting silence is
        # meaningless and the log-of-tiny-fraction path would saturate the
        # lift cap purely because the source is near zero.
        if src_val_raw < _EMPTY_BAND_THRESHOLD:
            per_band[band] = 0.0
            continue
        src_val = max(_FRACTION_FLOOR, src_val_raw)
        tgt_val = max(_FRACTION_FLOOR, float(target.get(band, 0.0)))
        raw_delta = 10.0 * math.log10(tgt_val / src_val)
        k = k_lift if raw_delta > 0 else k_cut
        applied = k * math.tanh(raw_delta / k)
        per_band[band] = applied

    # Map 7 fingerprint bands → 5 EQ shelves.
    # The low_shelf at 200 Hz covers sub_bass (20-60) + bass (60-250);
    # the high_shelf at 8 kHz covers presence (4-6k) + air (6-20k);
    # high_mid at 4 kHz straddles upper_mid (2-4k) and the bottom of presence.
    low_shelf  = (per_band['sub_bass_pct'] + per_band['bass_pct']) / 2.0
    low_mid    = per_band['low_mid_pct']
    mid        = per_band['mid_pct']
    high_mid   = (per_band['upper_mid_pct'] * 2.0 + per_band['presence_pct']) / 3.0
    high_shelf = (per_band['presence_pct'] + per_band['air_pct']) / 2.0

    return DeltaEQResult(
        low_shelf_gain=low_shelf,
        low_mid_gain=low_mid,
        mid_gain=mid,
        high_mid_gain=high_mid,
        high_shelf_gain=high_shelf,
        per_band_delta_db=per_band,
    )


def to_eq_curve(result: DeltaEQResult) -> dict[str, float]:
    """Render a DeltaEQResult into the dict shape expected by ProcessingParameters.

    Frequencies are kept at the established hand-tuned values (200 Hz low,
    500 Hz low-mid, 1.5 kHz mid, 4 kHz high-mid, 8 kHz high shelf) — those
    are perceptual choices independent of the new delta math.
    """
    return {
        'low_shelf_gain':  result.low_shelf_gain,
        'low_mid_gain':    result.low_mid_gain,
        'mid_gain':        result.mid_gain,
        'high_mid_gain':   result.high_mid_gain,
        'high_shelf_gain': result.high_shelf_gain,
        'low_shelf_freq':  200,
        'low_mid_freq':    500,
        'mid_freq':        1500,
        'high_mid_freq':   4000,
        'high_shelf_freq': 8000,
    }


__all__ = [
    "BAND_CAPS_DB",
    "DeltaEQResult",
    "compute_delta_eq",
    "to_eq_curve",
]
