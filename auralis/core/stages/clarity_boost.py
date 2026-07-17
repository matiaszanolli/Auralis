"""Clarity Boost Stage — focused Up-Mid bell boost for buried vocals/snare attack."""

from typing import TYPE_CHECKING

import numpy as np

from . import no_op

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
    hf_lift: float = 1.0,
    bass_pct: float = 0.0,
    mid_pct: float = 0.0,
) -> tuple[np.ndarray, dict | None]:
    """Apply a focused Up-Mid bell boost (1.5-3.5 kHz) for sources where
    vocal consonants and snare attack are buried.

    Two independent triggers — the stronger wins:

    1. **Absolute Up-Mid deficit** (original): Up-Mid below CLARITY_TOL_LOW
       (= p25 of the 27-track reference). Capped at CLARITY_MAX_BOOST_DB.
    2. **Relative vocal masking** (new): the voice band (mid + Up-Mid) is buried
       under a dominant bass — ``bass_pct / (mid_pct + upper_mid_pct)`` above
       VOCAL_MASK_RATIO_LOW. Capped at VOCAL_MASK_MAX_BOOST_DB. This catches the
       common case (Patricio Rey's Gulp: bass 60% / mid 5%) where Up-Mid is
       nominally fine but the voice is 6-9 dB under the bass, so trigger 1 never
       fired. Balanced bass-heavy genres (reggae/folk, ratio ~2) stay untouched.

    The masking trigger needs ``bass_pct``/``mid_pct``; callers that omit them
    (loud branches) default to 0.0, disabling trigger 2 — behaviour-preserving.

    Args:
        audio: Audio array [channels, samples]
        upper_mid_pct: Fingerprint upper-mid percentage (0-1)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for threshold constants
        hf_lift: Shared HF-budget multiplier (0-1) from ``hf_budget`` — restrains
            stacking with the exciter/presence/air stages on HF-dead sources.
        bass_pct: Fingerprint bass percentage (0-1), for the masking trigger.
        mid_pct: Fingerprint mid percentage (0-1), for the masking trigger.

    Returns:
        (processed_audio, stage_info) or (audio, None) if no boost applied
    """
    intensity = min(intensity, 1.0)

    # Trigger 1 — absolute Up-Mid deficit (capped at CLARITY_MAX_BOOST_DB).
    deficit = max(0.0, config.CLARITY_TOL_LOW - upper_mid_pct)
    deficit_factor = SmoothCurveUtilities.ramp_to_s_curve(
        deficit, 0.0, config.CLARITY_BOOST_RANGE_PCT
    )
    deficit_boost = config.CLARITY_MAX_BOOST_DB * deficit_factor

    # Trigger 2 — relative vocal masking (capped at VOCAL_MASK_MAX_BOOST_DB).
    voice_pct = mid_pct + upper_mid_pct
    mask_ratio = bass_pct / voice_pct if voice_pct > 1e-3 else 0.0
    mask_factor = SmoothCurveUtilities.vocal_mask_factor(
        bass_pct, mid_pct, upper_mid_pct,
        config.VOCAL_MASK_RATIO_LOW, config.VOCAL_MASK_RATIO_RANGE
    )
    mask_boost = config.VOCAL_MASK_MAX_BOOST_DB * mask_factor

    # Absolute-floor temper: amplifying near-silence is noise amplification.
    ABSOLUTE_FLOOR_PCT = 0.005
    if upper_mid_pct < ABSOLUTE_FLOOR_PCT:
        floor_temper = 0.5 + 0.5 * (upper_mid_pct / ABSOLUTE_FLOOR_PCT)
    else:
        floor_temper = 1.0

    # Stronger trigger wins; HF-budget + floor temper apply to both.
    boost_db = max(deficit_boost, mask_boost) * intensity * floor_temper * hf_lift

    if boost_db < 0.3:
        return no_op(audio)

    processed = ParallelEQUtilities.apply_bandpass_boost(
        audio,
        boost_db=boost_db,
        low_hz=config.CLARITY_LOW_HZ,
        high_hz=config.CLARITY_HIGH_HZ,
        sample_rate=sample_rate,
    )

    driver = "masking" if mask_boost > deficit_boost else "deficit"
    if verbose:
        print(
            f"   Clarity boost: +{boost_db:.1f} dB @ "
            f"{config.CLARITY_LOW_HZ:.0f}-{config.CLARITY_HIGH_HZ:.0f}Hz "
            f"({driver}; Up-Mid {upper_mid_pct:.1%}, bass/voice {mask_ratio:.1f})"
        )

    return processed, {
        'stage': 'clarity_boost',
        'boost_db': boost_db,
        'upper_mid_pct': upper_mid_pct,
        'driver': driver,
        'mask_ratio': mask_ratio,
    }
