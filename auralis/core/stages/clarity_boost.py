"""Clarity Boost Stage — focused Up-Mid bell boost for buried vocals/snare attack."""

from typing import TYPE_CHECKING

import numpy as np

from ..dsp import ParallelEQUtilities
from ..utils import SmoothCurveUtilities

if TYPE_CHECKING:
    from ..mastering_config import SimpleMasteringConfig


def apply(
    audio: np.ndarray,
    upper_mid_pct: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    config: 'SimpleMasteringConfig',
) -> tuple[np.ndarray, dict | None]:
    """Apply a focused Up-Mid bell boost (1.5-3.5 kHz) for sources where
    vocal consonants and snare attack are buried.

    Tolerance-band trigger: bypasses cleanly when Up-Mid is at or above
    CLARITY_TOL_LOW (= p25 of 27-track reference distribution).

    Args:
        audio: Audio array [channels, samples]
        upper_mid_pct: Fingerprint upper-mid percentage (0-1)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for threshold constants

    Returns:
        (processed_audio, stage_info) or (audio, None) if no boost applied
    """
    tol_low = config.CLARITY_TOL_LOW
    if upper_mid_pct >= tol_low:
        return audio, None

    deficit = tol_low - upper_mid_pct
    deficit_factor = SmoothCurveUtilities.ramp_to_s_curve(
        deficit, 0.0, config.CLARITY_BOOST_RANGE_PCT
    )

    # Absolute-floor temper: amplifying near-silence is noise amplification.
    ABSOLUTE_FLOOR_PCT = 0.005
    if upper_mid_pct < ABSOLUTE_FLOOR_PCT:
        floor_temper = 0.5 + 0.5 * (upper_mid_pct / ABSOLUTE_FLOOR_PCT)
    else:
        floor_temper = 1.0

    max_boost = config.CLARITY_MAX_BOOST_DB * intensity
    boost_db = max_boost * deficit_factor * floor_temper

    if boost_db < 0.3:
        return audio, None

    processed = ParallelEQUtilities.apply_bandpass_boost(
        audio,
        boost_db=boost_db,
        low_hz=config.CLARITY_LOW_HZ,
        high_hz=config.CLARITY_HIGH_HZ,
        sample_rate=sample_rate,
    )

    if verbose:
        print(
            f"   Clarity boost: +{boost_db:.1f} dB @ "
            f"{config.CLARITY_LOW_HZ:.0f}-{config.CLARITY_HIGH_HZ:.0f}Hz "
            f"(Up-Mid {upper_mid_pct:.1%})"
        )

    return processed, {
        'stage': 'clarity_boost',
        'boost_db': boost_db,
        'upper_mid_pct': upper_mid_pct,
    }
