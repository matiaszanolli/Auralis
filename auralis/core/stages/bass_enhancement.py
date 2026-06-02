"""Bass Enhancement Stage — tolerance-band bass EQ (boost thin / cut muddy)."""

from typing import TYPE_CHECKING

import numpy as np

from ..dsp import ParallelEQUtilities
from ..utils import SmoothCurveUtilities

if TYPE_CHECKING:
    from ..mastering_config import SimpleMasteringConfig


def apply(
    audio: np.ndarray,
    bass_pct: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    config: 'SimpleMasteringConfig',
) -> tuple[np.ndarray, dict | None]:
    """Tolerance-band bass balance.

    Does nothing while the source sits inside [BASS_TOL_LOW, BASS_TOL_HIGH].
    Only corrects when outside the band, ramping smoothly from the nearest edge.

    - **Boost path**: low-shelf at 100 Hz when bass_pct < BASS_TOL_LOW.
    - **Cut path**: bell at 100-220 Hz when bass_pct > BASS_TOL_HIGH.

    Args:
        audio: Stereo audio [channels, samples]
        bass_pct: Fingerprint bass percentage (0-1)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for threshold constants

    Returns:
        (processed_audio, stage_info) or (audio, None) if no correction applied
    """
    tol_low = config.BASS_TOL_LOW
    tol_high = config.BASS_TOL_HIGH

    deficit = max(0.0, tol_low - bass_pct)
    boost_factor = SmoothCurveUtilities.ramp_to_s_curve(deficit, 0.0, config.BASS_BOOST_RANGE_PCT)
    boost_db = config.MAX_BASS_BOOST_DB * intensity * boost_factor

    excess = max(0.0, bass_pct - tol_high)
    cut_factor = SmoothCurveUtilities.ramp_to_s_curve(excess, 0.0, config.BASS_CUT_RANGE_PCT)
    cut_db = -config.MAX_BASS_CUT_DB * intensity * cut_factor

    AUDIBILITY_FLOOR_DB = 0.3
    applied = []
    processed = audio

    if boost_db >= AUDIBILITY_FLOOR_DB:
        processed = ParallelEQUtilities.apply_low_shelf_boost(
            processed,
            boost_db=boost_db,
            freq_hz=config.BASS_SHELF_HZ,
            sample_rate=sample_rate,
        )
        applied.append(f"+{boost_db:.1f}dB <{config.BASS_SHELF_HZ:.0f}Hz")

    if abs(cut_db) >= AUDIBILITY_FLOOR_DB:
        processed = ParallelEQUtilities.apply_bandpass_boost(
            processed,
            boost_db=cut_db,
            low_hz=config.BASS_DEMUD_LOW_HZ,
            high_hz=config.BASS_DEMUD_HIGH_HZ,
            sample_rate=sample_rate,
        )
        applied.append(f"{cut_db:.1f}dB @{config.BASS_DEMUD_LOW_HZ:.0f}-{config.BASS_DEMUD_HIGH_HZ:.0f}Hz")

    if not applied:
        return audio, None

    if verbose:
        print(f"   Bass balance: {' / '.join(applied)}  (bass={bass_pct:.0%})")

    return processed, {
        'stage': 'bass_balance',
        'boost_db': boost_db,
        'cut_db': cut_db,
        'bass_pct': bass_pct,
    }
