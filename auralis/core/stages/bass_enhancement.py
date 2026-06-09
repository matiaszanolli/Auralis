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
    mid_pct: float = 0.0,
    upper_mid_pct: float = 0.0,
) -> tuple[np.ndarray, dict | None]:
    """Tolerance-band bass balance + vocal de-masking.

    Does nothing while the source sits inside [BASS_TOL_LOW, BASS_TOL_HIGH] and
    the voice is not masked. Otherwise:

    - **Boost path**: low-shelf at 100 Hz when bass_pct < BASS_TOL_LOW.
    - **Cut path**: bell at 100-220 Hz when bass_pct > BASS_TOL_HIGH.
    - **De-mask path**: extra 150-450 Hz cut when the voice is buried under a
      dominant bass (high bass/voice ratio). Keyed on the SAME masking severity
      as the clarity-boost lift, so the two halves of the unmasking move stay in
      step — lift the voice AND lower the masker. Preserves the 50-120 Hz kick.
      ``mid_pct``/``upper_mid_pct`` default to 0.0 → de-mask disabled, so the
      loud branches keep their existing behaviour.

    Args:
        audio: Stereo audio [channels, samples]
        bass_pct: Fingerprint bass percentage (0-1)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for threshold constants
        mid_pct: Fingerprint mid percentage (0-1), for the de-mask trigger.
        upper_mid_pct: Fingerprint upper-mid percentage (0-1), for de-mask.

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

    # De-mask cut: lower the masking upper-bass/low-mid when the voice is buried.
    mask_factor = SmoothCurveUtilities.vocal_mask_factor(
        bass_pct, mid_pct, upper_mid_pct,
        config.VOCAL_MASK_RATIO_LOW, config.VOCAL_MASK_RATIO_RANGE
    )
    demask_db = -config.VOCAL_MASK_BASS_CUT_DB * intensity * mask_factor

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

    if abs(demask_db) >= AUDIBILITY_FLOOR_DB:
        processed = ParallelEQUtilities.apply_bandpass_boost(
            processed,
            boost_db=demask_db,
            low_hz=config.VOCAL_MASK_CUT_LOW_HZ,
            high_hz=config.VOCAL_MASK_CUT_HIGH_HZ,
            sample_rate=sample_rate,
        )
        applied.append(f"de-mask {demask_db:.1f}dB @{config.VOCAL_MASK_CUT_LOW_HZ:.0f}-{config.VOCAL_MASK_CUT_HIGH_HZ:.0f}Hz")

    if not applied:
        return audio.copy(), None

    if verbose:
        print(f"   Bass balance: {' / '.join(applied)}  (bass={bass_pct:.0%})")

    return processed, {
        'stage': 'bass_balance',
        'boost_db': boost_db,
        'cut_db': cut_db,
        'demask_db': demask_db,
        'bass_pct': bass_pct,
    }
