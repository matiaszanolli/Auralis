"""Sub-Bass Control Stage — adaptive 20-60Hz tightening."""

from typing import TYPE_CHECKING

import numpy as np
from scipy.signal import butter, sosfilt

from ..dsp import ParallelEQUtilities
from ..utils import SmoothCurveUtilities

if TYPE_CHECKING:
    from ..mastering_config import SimpleMasteringConfig


def apply(
    audio: np.ndarray,
    sub_bass_pct: float,
    bass_pct: float,
    intensity: float,
    sample_rate: int,
    verbose: bool,
    config: 'SimpleMasteringConfig',
) -> tuple[np.ndarray, dict | None]:
    """Apply adaptive sub-bass control (20-60Hz).

    High sub-bass → tighten (reduce rumble). Inside the tolerance band
    (sub_bass_pct ≤ SUB_TOL_HIGH) no action is taken. HP filter reserved
    for pathological rumble (> SUB_HP_ACTIVATE_PCT).

    Args:
        audio: Audio array [channels, samples]
        sub_bass_pct: Fingerprint sub-bass percentage (0-1)
        bass_pct: Fingerprint bass percentage (0-1)
        intensity: Processing intensity 0.0-1.0
        sample_rate: Audio sample rate in Hz
        verbose: Print progress
        config: SimpleMasteringConfig instance for threshold constants

    Returns:
        (processed_audio, stage_info) or (audio, None) if no action taken
    """
    excess = max(0.0, sub_bass_pct - config.SUB_TOL_HIGH)
    excess_factor = SmoothCurveUtilities.ramp_to_s_curve(excess, 0.0, config.SUB_CUT_RANGE_PCT)
    reduction_db = config.MAX_SUB_CUT_DB * intensity * excess_factor

    processed = audio
    if abs(reduction_db) >= 0.1:
        processed = ParallelEQUtilities.apply_low_shelf_boost(
            processed,
            boost_db=reduction_db,
            freq_hz=config.SUB_BASS_CUTOFF_HZ,
            sample_rate=sample_rate,
        )

    # HP only for severely excessive sub-bass (well above musical kick/bass range)
    applied_hp = False
    if sub_bass_pct >= config.SUB_HP_ACTIVATE_PCT:
        nyq = sample_rate / 2.0
        # Floor is a numerical-stability minimum, NOT a musical cutoff. The old
        # 0.005 floor mapped to 110 Hz @ 44.1 kHz, so the 25 Hz rumble HP
        # actually high-passed at 110 Hz and gutted the whole bass region when
        # it fired (#4211). butter(order<=2) is stable down to ~1e-4 normalized.
        hp_norm = min(0.99, max(1e-4, config.SUBBASS_HP_FREQ_HZ / nyq))
        hp_sos = butter(config.SUBBASS_HP_ORDER, hp_norm, btype='high', output='sos')
        axis = -1 if processed.ndim > 1 else 0
        processed = np.asarray(sosfilt(hp_sos, processed, axis=axis), dtype=processed.dtype)
        applied_hp = True

    if abs(reduction_db) < 0.1 and not applied_hp:
        return audio.copy(), None

    if verbose:
        msg = f"   Sub-bass tighten: {reduction_db:.1f} dB @ <{config.SUB_BASS_CUTOFF_HZ:.0f}Hz"
        if applied_hp:
            msg += (f" + HP @ {config.SUBBASS_HP_FREQ_HZ:.0f}Hz "
                    f"(order {config.SUBBASS_HP_ORDER})")
        print(msg)

    return processed, {
        'stage': 'sub_bass_control',
        'reduction_db': reduction_db,
        'sub_bass_pct': sub_bass_pct,
        'hp_applied': applied_hp,
    }
