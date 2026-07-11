"""
Mastering Notch Band-Context Scaling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Scales detected resonance-notch depths by how energized their target
frequency band already is, so notching doesn't gouge an already-deficient
band.

Extracted from simple_mastering.py's _contextualize_notches (#4072), used by
mastering_prepare.prepare_file.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import TYPE_CHECKING

from .dsp import Notch

if TYPE_CHECKING:
    from .mastering_config import SimpleMasteringConfig


def contextualize_notches(
    notches: list[Notch], fingerprint: dict, config: 'SimpleMasteringConfig'
) -> list[Notch]:
    """
    Filter and scale each notch's depth based on the target band's health.

    Three regimes (driven by `band_pct / band_target` ratio):

    - **health ≥ NOTCH_CAPPED_HEALTH (≥0.7)**: full notch — band is well-
      energized, scaling depth proportionally is safe.
    - **NOTCH_MIN_BAND_HEALTH ≤ health < NOTCH_CAPPED_HEALTH (0.6-0.7)**:
      allow the notch but hard-cap its depth to NOTCH_LOW_HEALTH_CAP_DB
      (e.g. -1 dB). The resonance is real but we tread lightly because
      the band is borderline thin.
    - **health < NOTCH_MIN_BAND_HEALTH (<0.6)**: skip entirely. Notching
      an already-deficient band makes the perceived scoop worse than
      leaving the resonance alone.

    These thresholds were tuned from A/B analysis on a source where Mid
    was at 53% of target — proportional scaling alone still produced
    -2.2 pp of additional Mid scoop, contributing to the perceived
    'high-passed' sound.
    """
    if not notches:
        return notches

    # Map (low, high) Hz → fingerprint key name → reference target (median
    # across n=27 reference tracks across 8 genres). The previous values
    # were "pop-master" theoretical numbers; these are measured medians
    # from actual well-mastered records. Critically: presence/brillance/air
    # targets used to be 11%/6%/4% which made even normal records appear
    # "deficient" — now correctly set to ~1.5%/0.4%/0.1%.
    BAND_LOOKUP = [
        ((20, 60),       'sub_bass_pct',   0.087),
        ((60, 250),      'bass_pct',       0.460),
        ((250, 500),     'low_mid_pct',    0.136),
        ((500, 2000),    'mid_pct',        0.171),
        ((2000, 4000),   'upper_mid_pct',  0.055),
        ((4000, 8000),   'presence_pct',   0.015),
        ((8000, 12000),  'brilliance_pct', 0.004),
        ((12000, 24000), 'air_pct',        0.001),
    ]

    out: list[Notch] = []
    for n in notches:
        # Find which band this notch lands in
        band_pct = None
        band_target = None
        for (lo, hi), key, tgt in BAND_LOOKUP:
            if lo <= n.freq_hz < hi:
                band_pct = fingerprint.get(key, tgt)
                band_target = tgt
                break

        if band_pct is None or band_target is None:
            out.append(n)
            continue

        # Health metric: ratio of actual to target energy share, capped at 1.0.
        # 1.0 = well-energized band, 0.5 = half-energized, etc.
        health = min(1.0, band_pct / band_target) if band_target > 0 else 1.0

        if health < config.NOTCH_MIN_BAND_HEALTH:
            # Band is severely deficient — leave the resonance alone.
            continue

        # Proportional scaling for moderately-deficient bands. The 0.7+
        # zone gets full proportional depth; the 0.6-0.7 zone is capped
        # to a hard floor regardless of the configured max depth.
        scaled_depth = n.depth_db * health

        if health < config.NOTCH_CAPPED_HEALTH:
            # Cap to the low-health cap (compare absolute values; both negative)
            if abs(scaled_depth) > abs(config.NOTCH_LOW_HEALTH_CAP_DB):
                scaled_depth = config.NOTCH_LOW_HEALTH_CAP_DB

        out.append(Notch(freq_hz=n.freq_hz, depth_db=scaled_depth, q=n.q))

    return out
