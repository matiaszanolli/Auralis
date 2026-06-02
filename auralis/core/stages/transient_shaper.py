"""Transient Shaper Stage — restore kick/bass attack on compressed low-end."""

from typing import TYPE_CHECKING

import numpy as np

from ..dsp import TransientShaper
from ..utils import SmoothCurveUtilities

if TYPE_CHECKING:
    from ..mastering_config import SimpleMasteringConfig


def apply(
    audio: np.ndarray,
    bass_pct: float,
    low_mid_pct: float,
    crest_db: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    config: 'SimpleMasteringConfig',
) -> tuple[np.ndarray, dict | None]:
    """Restore kick/bass attack on compressed low-end.

    Activates when the overall crest factor suggests the bass/lo-mid bands
    have been compressed flat. Global crest <= TRANSIENT_ACTIVATE_CREST_DB is
    a strong signal that the low end has been levelled.

    Args:
        audio: Audio array [channels, samples]
        bass_pct: Fingerprint bass percentage (0-1)
        low_mid_pct: Fingerprint low-mid percentage (0-1)
        crest_db: Global crest factor in dB
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for threshold constants

    Returns:
        (processed_audio, stage_info) or (audio, None) if stage did not fire
    """
    threshold = config.TRANSIENT_ACTIVATE_CREST_DB
    if crest_db >= threshold:
        return audio.copy(), None

    # Compressed-ness factor: 0 at threshold, 1 at very compressed (8 dB)
    compress_factor = SmoothCurveUtilities.ramp_to_s_curve(
        threshold - crest_db, 0.0, threshold - 8.0
    )

    max_boost = config.TRANSIENT_MAX_BOOST_DB * intensity
    boost_db = max_boost * compress_factor

    if boost_db < 0.5:
        return audio.copy(), None

    processed = audio
    # Bass band — skip if essentially no bass to shape
    if bass_pct >= 0.05:
        processed = TransientShaper.apply(
            processed, sample_rate,
            band_low_hz=config.TRANSIENT_BASS_LOW_HZ,
            band_high_hz=config.TRANSIENT_BASS_HIGH_HZ,
            attack_boost_db=boost_db,
        )

    # Lo-mid band — slightly gentler boost (lo-mid attacks are less critical)
    if low_mid_pct >= 0.05:
        processed = TransientShaper.apply(
            processed, sample_rate,
            band_low_hz=config.TRANSIENT_LO_MID_LOW_HZ,
            band_high_hz=config.TRANSIENT_LO_MID_HIGH_HZ,
            attack_boost_db=boost_db * 0.7,
        )

    if verbose:
        print(
            f"   Transient shaper: +{boost_db:.1f} dB attack on "
            f"{config.TRANSIENT_BASS_LOW_HZ:.0f}-{config.TRANSIENT_BASS_HIGH_HZ:.0f}Hz "
            f"(crest {crest_db:.1f} dB)"
        )

    return processed, {
        'stage': 'transient_shaper',
        'boost_db': boost_db,
        'crest_db': crest_db,
    }
