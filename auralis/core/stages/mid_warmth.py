"""Mid Warmth Stage — adaptive 200-2kHz body boost for thin mixes."""

from typing import TYPE_CHECKING

import numpy as np

from . import no_op

from ..dsp import ParallelEQUtilities
from ..utils import SmoothCurveUtilities

if TYPE_CHECKING:
    from ..mastering_config import SimpleMasteringConfig


def apply(
    audio: np.ndarray,
    low_mid_pct: float,
    mid_pct: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    config: 'SimpleMasteringConfig',
) -> tuple[np.ndarray, dict | None]:
    """Apply adaptive mid-range warmth (200-2kHz body).

    Boosts when the combined low-mid + mid body content is below 25%.
    Uses smooth curves throughout — no hard thresholds.

    Args:
        audio: Audio array [channels, samples]
        low_mid_pct: Fingerprint low-mid percentage (0-1)
        mid_pct: Fingerprint mid percentage (0-1)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for frequency constants

    Returns:
        (processed_audio, stage_info) or (audio, None) if no boost applied
    """
    body_content = (low_mid_pct + mid_pct) / 2.0

    if body_content >= 0.25:
        return no_op(audio)

    body_factor = 1.0 - SmoothCurveUtilities.ramp_to_s_curve(body_content, 0.0, 0.25)

    max_boost_db = 1.5 * intensity
    boost_db = max_boost_db * body_factor

    if boost_db < 0.3:
        return no_op(audio)

    processed = ParallelEQUtilities.apply_bandpass_boost(
        audio,
        boost_db=boost_db,
        low_hz=config.MID_BODY_LOW_HZ,
        high_hz=config.MID_BODY_HIGH_HZ,
        sample_rate=sample_rate,
    )

    if verbose:
        print(f"   Mid warmth: +{boost_db:.1f} dB @ {config.MID_BODY_LOW_HZ:.0f}-{config.MID_BODY_HIGH_HZ:.0f}Hz")

    return processed, {
        'stage': 'mid_warmth',
        'boost_db': boost_db,
        'body_content': body_content,
    }
