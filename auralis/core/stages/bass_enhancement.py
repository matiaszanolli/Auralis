"""Bass Enhancement Stage — bass balance and spectral counterweight."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from ..dsp import ParallelEQUtilities
from ..utils import SmoothCurveUtilities
from . import no_op

if TYPE_CHECKING:
    from ..mastering_config import SimpleMasteringConfig


def apply(
    audio: np.ndarray,
    bass_pct: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    config: SimpleMasteringConfig,
    mid_pct: float = 0.0,
    upper_mid_pct: float = 0.0,
    presence_pct: float = 0.0,
) -> tuple[np.ndarray, dict[str, Any] | None]:
    """Bass balance, continuous spectral counterweight, and vocal de-masking.

    - **Balance path**: a signed low shelf follows bass distance from the
      508-source corpus median through a smooth tanh response. There is no
      tolerance band or pass/fail boundary.
    - **De-mask path**: extra 150-450 Hz cut when the voice is buried under a
      dominant bass (high bass/voice ratio). Keyed on the SAME masking severity
      as the clarity-boost lift, so the two halves of the unmasking move stay in
      step — lift the voice AND lower the masker. Preserves the 50-120 Hz kick.
      ``mid_pct``/``upper_mid_pct`` default to 0.0 → de-mask disabled, so the
      loud branches keep their existing behaviour.
    - **Counterweight path**: a small low shelf follows the corpus-calibrated
      log ratio of upper-mid/presence energy to bass. Bright-leaning sources
      receive more weight smoothly; there is no source label or activation
      boundary.

    Args:
        audio: Stereo audio [channels, samples]
        bass_pct: Fingerprint bass percentage (0-1)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for mastering constants
        mid_pct: Fingerprint mid percentage (0-1), for the de-mask trigger.
        upper_mid_pct: Fingerprint upper-mid percentage (0-1), for de-mask.
        presence_pct: Fingerprint presence percentage (0-1), for the continuous
            high-to-bass counterweight.

    Returns:
        (processed_audio, stage_info) or (audio, None) if no correction applied
    """
    intensity = float(np.clip(intensity, 0.0, 1.0))
    bass_balance_z = (
        config.BASS_TARGET_PCT - bass_pct
    ) / config.BASS_BALANCE_SCALE_PCT
    balance_db = (
        config.MAX_BASS_BALANCE_DB
        * intensity
        * np.tanh(bass_balance_z)
    )

    high_to_bass_log = float(
        np.log(
            (upper_mid_pct + presence_pct + config.BASS_TILT_EPSILON)
            / (bass_pct + config.BASS_TILT_EPSILON)
        )
    )
    tilt_z = (
        high_to_bass_log - config.BASS_TILT_LOG_MEDIAN
    ) / config.BASS_TILT_LOG_SCALE
    counterweight_factor = 0.5 + 0.5 * np.tanh(
        (tilt_z - config.BASS_COUNTERWEIGHT_CENTER_Z)
        / config.BASS_COUNTERWEIGHT_WIDTH_Z
    )
    counterweight_db = (
        config.MAX_BASS_COUNTERWEIGHT_DB
        * intensity
        * counterweight_factor
    )
    shelf_db = balance_db + counterweight_db
    boost_db = max(0.0, shelf_db)
    cut_db = min(0.0, shelf_db)

    # De-mask cut: lower the masking upper-bass/low-mid when the voice is buried.
    mask_factor = SmoothCurveUtilities.vocal_mask_factor(
        bass_pct, mid_pct, upper_mid_pct,
        config.VOCAL_MASK_RATIO_LOW, config.VOCAL_MASK_RATIO_RANGE
    )
    demask_db = -config.VOCAL_MASK_BASS_CUT_DB * intensity * mask_factor

    numerical_zero = np.finfo(np.float64).eps
    applied = []
    processed = audio

    if abs(shelf_db) > numerical_zero:
        processed = ParallelEQUtilities.apply_low_shelf_boost(
            processed,
            boost_db=shelf_db,
            freq_hz=config.BASS_SHELF_HZ,
            sample_rate=sample_rate,
        )
        applied.append(
            f"{shelf_db:+.1f}dB <{config.BASS_SHELF_HZ:.0f}Hz"
        )

    if abs(demask_db) > numerical_zero:
        processed = ParallelEQUtilities.apply_bandpass_boost(
            processed,
            boost_db=demask_db,
            low_hz=config.VOCAL_MASK_CUT_LOW_HZ,
            high_hz=config.VOCAL_MASK_CUT_HIGH_HZ,
            sample_rate=sample_rate,
        )
        applied.append(f"de-mask {demask_db:.1f}dB @{config.VOCAL_MASK_CUT_LOW_HZ:.0f}-{config.VOCAL_MASK_CUT_HIGH_HZ:.0f}Hz")

    if not applied:
        return no_op(audio)

    if verbose:
        print(f"   Bass balance: {' / '.join(applied)}  (bass={bass_pct:.0%})")

    return processed, {
        'stage': 'bass_balance',
        'boost_db': boost_db,
        'cut_db': cut_db,
        'balance_db': balance_db,
        'demask_db': demask_db,
        'counterweight_db': counterweight_db,
        'high_to_bass_z': tilt_z,
        'bass_pct': bass_pct,
    }
