"""Presence Enhancement Stage — adaptive 2-6kHz boost for dull mixes."""

from typing import TYPE_CHECKING

import numpy as np

from ..dsp import ParallelEQUtilities
from ..utils import SmoothCurveUtilities

if TYPE_CHECKING:
    from ..mastering_config import SimpleMasteringConfig


def apply(
    audio: np.ndarray,
    presence_pct: float,
    upper_mid_pct: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    config: 'SimpleMasteringConfig',
) -> tuple[np.ndarray, dict | None]:
    """Apply adaptive presence enhancement for dull mixes (2-6kHz boost).

    Boosts presence frequencies to add clarity, definition, and forward
    character. Only fires when the combined 2-6kHz content is below 30%.

    Args:
        audio: Audio array [channels, samples]
        presence_pct: Fingerprint presence percentage (4-6kHz, 0-1)
        upper_mid_pct: Fingerprint upper-mid percentage (2-4kHz, 0-1)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for frequency constants

    Returns:
        (processed_audio, stage_info) or (audio, None) if no enhancement applied
    """
    presence_content = (presence_pct + upper_mid_pct) / 2.0

    if presence_content >= 0.30:
        return audio, None

    presence_factor = 1.0 - SmoothCurveUtilities.ramp_to_s_curve(presence_content, 0.0, 0.30)

    max_boost_db = 2.0 * intensity
    boost_db = max_boost_db * presence_factor

    if boost_db < 0.3:
        return audio, None

    processed = ParallelEQUtilities.apply_bandpass_boost(
        audio,
        boost_db=boost_db,
        low_hz=config.PRESENCE_LOW_HZ,
        high_hz=config.PRESENCE_HIGH_HZ,
        sample_rate=sample_rate,
    )

    if verbose:
        print(f"   Presence enhance: +{boost_db:.1f} dB @ {config.PRESENCE_LOW_HZ:.0f}-{config.PRESENCE_HIGH_HZ:.0f}Hz")

    return processed, {
        'stage': 'presence_enhance',
        'boost_db': boost_db,
        'presence_content': presence_content,
    }
