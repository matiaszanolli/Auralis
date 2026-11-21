"""Mid Warmth Stage — adaptive 200-2kHz body boost for thin mixes."""

from typing import TYPE_CHECKING, Any

import numpy as np

from .deficit_boost import deficit_bandpass_boost

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
) -> tuple[np.ndarray, dict[str, Any] | None]:
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
    return deficit_bandpass_boost(
        audio,
        content=(low_mid_pct + mid_pct) / 2.0,
        threshold=0.25,
        max_boost_db=config.MAX_MID_BOOST_DB * intensity,
        low_hz=config.MID_BODY_LOW_HZ,
        high_hz=config.MID_BODY_HIGH_HZ,
        sample_rate=sample_rate,
        verbose=verbose,
        label="Mid warmth",
        stage='mid_warmth',
        content_key='body_content',
    )
