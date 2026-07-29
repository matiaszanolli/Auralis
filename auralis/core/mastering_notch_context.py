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

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .dsp import Notch

if TYPE_CHECKING:
    from .mastering_config import SimpleMasteringConfig


def contextualize_notches(
    notches: list[Notch],
    fingerprint: dict[str, float],
    config: SimpleMasteringConfig,
) -> list[Notch]:
    """
    Scale notch depth continuously from band health and frequency context.

    A smooth health response makes notches asymptotically disappear in an
    already-thin band without a skip threshold. Low-frequency musical peaks
    receive additional protection. Finally, tanh compression limits both each
    notch and the cumulative depth of clustered notches without a hard cap.
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
    band_groups: list[int] = []
    for n in notches:
        # Find which band this notch lands in
        band_pct = None
        band_target = None
        band_group = -1
        for index, ((lo, hi), key, tgt) in enumerate(BAND_LOOKUP):
            if lo <= n.freq_hz < hi:
                band_pct = fingerprint.get(key, tgt)
                band_target = tgt
                band_group = index
                break

        if band_pct is None or band_target is None:
            out.append(n)
            band_groups.append(band_group)
            continue

        # Health metric: ratio of actual to target energy share, capped at 1.0.
        # 1.0 = well-energized band, 0.5 = half-energized, etc.
        health = min(1.0, band_pct / band_target) if band_target > 0 else 1.0
        health_response = 0.5 + 0.5 * math.tanh(
            (health - config.NOTCH_HEALTH_RESPONSE_CENTER)
            / config.NOTCH_HEALTH_RESPONSE_WIDTH
        )
        scaled_depth = n.depth_db * health * health_response

        # Smooth per-notch depth compression. Small cuts stay close to their
        # measured depth, while large PSD peaks cannot dominate the tonal curve.
        depth_sign = -1.0 if scaled_depth < 0.0 else 1.0
        depth_magnitude = config.NOTCH_SOFT_MAX_DEPTH_DB * math.tanh(
            abs(scaled_depth) / config.NOTCH_SOFT_MAX_DEPTH_DB
        )
        scaled_depth = depth_sign * depth_magnitude

        # Low-frequency PSD peaks are often sustained notes or harmonics rather
        # than room/honk resonances. Protect that musical region continuously:
        # below the transition center cuts become both shallower and narrower,
        # while midrange detections retain their measured depth.
        transition = 0.5 + 0.5 * math.tanh(
            (n.freq_hz - config.NOTCH_LOW_PROTECTION_CENTER_HZ)
            / config.NOTCH_LOW_PROTECTION_WIDTH_HZ
        )
        depth_scale = (
            config.NOTCH_LOW_PROTECTION_FLOOR
            + (1.0 - config.NOTCH_LOW_PROTECTION_FLOOR) * transition
        )
        protected_depth = scaled_depth * depth_scale
        protected_q = n.q * (2.0 - depth_scale)

        out.append(
            Notch(
                freq_hz=n.freq_hz,
                depth_db=protected_depth,
                q=protected_q,
            )
        )
        band_groups.append(band_group)

    # Smooth cumulative-depth budget for clustered notches in the same broad
    # fingerprint band. This prevents three individually plausible detections
    # from combining into a broad 3-4 dB scoop.
    for band_group in set(band_groups):
        indices = [
            index
            for index, group in enumerate(band_groups)
            if group == band_group
        ]
        total_depth = sum(abs(out[index].depth_db) for index in indices)
        if total_depth <= 0.0:
            continue
        ratio = total_depth / config.NOTCH_SOFT_BAND_BUDGET_DB
        budget_scale = math.tanh(ratio) / ratio
        for index in indices:
            notch = out[index]
            out[index] = Notch(
                freq_hz=notch.freq_hz,
                depth_db=notch.depth_db * budget_scale,
                q=notch.q,
            )

    return out
