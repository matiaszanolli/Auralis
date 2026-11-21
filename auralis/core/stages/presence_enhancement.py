"""Presence Enhancement Stage — adaptive 2-6kHz boost for dull mixes."""

from typing import TYPE_CHECKING, Any

import numpy as np

from . import cap_additive_hf_intensity
from .deficit_boost import deficit_bandpass_boost

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
    hf_lift: float = 1.0,
) -> tuple[np.ndarray, dict[str, Any] | None]:
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
        hf_lift: Shared HF-budget multiplier (0-1) from ``hf_budget`` — restrains
            stacking with the exciter/clarity/air stages on HF-dead sources.

    Returns:
        (processed_audio, stage_info) or (audio, None) if no enhancement applied
    """
    intensity = cap_additive_hf_intensity(intensity)

    return deficit_bandpass_boost(
        audio,
        content=(presence_pct + upper_mid_pct) / 2.0,
        threshold=0.30,
        max_boost_db=config.MAX_PRESENCE_BOOST_DB * intensity,
        hf_lift=hf_lift,
        low_hz=config.PRESENCE_LOW_HZ,
        high_hz=config.PRESENCE_HIGH_HZ,
        sample_rate=sample_rate,
        verbose=verbose,
        label="Presence enhance",
        stage='presence_enhance',
        content_key='presence_content',
    )
