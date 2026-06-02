"""Air Enhancement Stage — adaptive 6-20kHz sparkle for dark mixes."""

from typing import TYPE_CHECKING

import numpy as np

from ..dsp import ParallelEQUtilities
from ..utils import SmoothCurveUtilities

if TYPE_CHECKING:
    from ..mastering_config import SimpleMasteringConfig


def apply(
    audio: np.ndarray,
    air_pct: float,
    spectral_rolloff: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    config: 'SimpleMasteringConfig',
) -> tuple[np.ndarray, dict | None]:
    """Apply adaptive air enhancement for dark mixes (6-20kHz sparkle).

    Boosts high frequencies to add air, sparkle, and openness. Uses both
    air_pct and spectral_rolloff to detect naturally dark material.
    Uses smooth curves — no hard thresholds.

    Args:
        audio: Audio array [channels, samples]
        air_pct: Fingerprint air percentage (6-20kHz, 0-1)
        spectral_rolloff: Frequency where most energy is below (0-1, normalized)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for frequency constants

    Returns:
        (processed_audio, stage_info) or (audio, None) if no enhancement applied
    """
    darkness_factor = (1.0 - air_pct) * 0.6 + (1.0 - spectral_rolloff) * 0.4

    if darkness_factor < 0.4:
        return audio.copy(), None

    air_factor = SmoothCurveUtilities.ramp_to_s_curve(darkness_factor, 0.4, 1.0)

    max_boost_db = 1.5 * intensity
    boost_db = max_boost_db * air_factor

    if boost_db < 0.3:
        return audio.copy(), None

    processed = ParallelEQUtilities.apply_high_shelf_boost(
        audio,
        boost_db=boost_db,
        freq_hz=config.AIR_SHELF_HZ,
        sample_rate=sample_rate,
    )

    if verbose:
        print(f"   Air enhance: +{boost_db:.1f} dB above {config.AIR_SHELF_HZ:.0f}Hz")

    return processed, {
        'stage': 'air_enhance',
        'boost_db': boost_db,
        'darkness_factor': darkness_factor,
    }
