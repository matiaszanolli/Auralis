"""
Continuous-Mode Guard Knees and Corrections
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Threshold knees and the two small measurement/correction helpers that
``ContinuousMode``'s cross-dimensional guards are built from.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Split out of ``continuous_mode.py`` (#4254). The knees are tuning data, not
pipeline logic — they belong next to each other where the whole guard schedule
can be read at a glance, rather than scattered above a 700-line class.
"""

import numpy as np

from ...dsp.utils.filters import is_long_enough_for_sosfiltfilt

# Cross-dimensional guard knees (#4860).
#
# Each pair brackets the hard threshold this guard used to switch on at, so
# behaviour well inside and well outside the old trigger is unchanged and only
# the transition is a ramp. Knees are deliberately centred on the old values:
#   EQ drift      1.5 dB  -> [1.0, 2.0]
#   spectral tilt 0.10    -> [0.05, 0.15]
#   phase drop    -0.2    -> [0.1, 0.3] (on the drop magnitude)
#   phase level   0.3     -> [0.4, 0.2] (descending: lower correlation = worse)
EQ_DRIFT_KNEE_START = 1.0
EQ_DRIFT_KNEE_END = 2.0
TILT_SHIFT_KNEE_START = 0.05
TILT_SHIFT_KNEE_END = 0.15
PHASE_DROP_KNEE_START = 0.1
PHASE_DROP_KNEE_END = 0.3
PHASE_LEVEL_KNEE_START = 0.4
PHASE_LEVEL_KNEE_END = 0.2
# Stereo-width clipping safety (#5108). The fourth guard in this file, and the
# one #4860 never migrated: it was a bare `if pre_peak_db > -2.0` skip that
# either applied full widening or none. Knee centred on that old -2.0 dBFS
# threshold so the far field is unchanged — full widening well below, unity
# (no widening) well above — and only the transition becomes a ramp.
WIDTH_PEAK_KNEE_START = -3.0
WIDTH_PEAK_KNEE_END = -2.0
MAX_PHASE_BLEND = 0.5

# Below these a correction is numerically pointless, not merely small. These
# are no-op cutoffs that exist to skip needless filter/copy work — NOT
# behavioural gates, so they must stay far below audibility (~0.01 dB is
# roughly three orders of magnitude under a just-noticeable level difference).
GUARD_EPSILON_DB = 0.01
GUARD_EPSILON_BLEND = 0.001


def _quick_3band(audio: np.ndarray, sample_rate: int) -> tuple[float, float, float]:
    """Fast 3-band energy split (reuses stage_snapshot logic inline for speed)."""
    from .stage_snapshot import _compute_3band_energy
    return _compute_3band_energy(audio, sample_rate)


def tilt_correction_db(bass_shift: float, high_shift: float) -> tuple[float, float]:
    """Spectral-tilt correction for a dynamics-stage energy shift: ``(dB, gate)``.

    The tilt is the DIFFERENCE of the two shifts: bass up or highs down both read
    as "more bass-heavy", and a shift of both in the same direction (the mid band
    changed) is no tilt at all. This used to pick whichever shift was larger by
    ``abs()``, so near a tie the correction jumped between the two drivers' values
    and flipped sign (#6121). A lone bass or high shift gives exactly the result it
    always did. Positive dB boosts bass / cuts highs; capped at ±2 dB.
    """
    # Call-time import: cross_dimensional_guard pulls in stage_snapshot -> base,
    # which import this module's package, so a module-level import is a cycle.
    from .cross_dimensional_guard import smooth_gate

    gate = smooth_gate(
        max(abs(bass_shift), abs(high_shift)), TILT_SHIFT_KNEE_START, TILT_SHIFT_KNEE_END
    )
    tilt_db = max(-2.0, min(2.0, -(bass_shift - high_shift) * 10.0))
    return tilt_db * gate, gate


def _apply_spectral_tilt_correction(
    audio: np.ndarray, tilt_db: float, sample_rate: int
) -> np.ndarray:
    """Apply a gentle spectral tilt correction using a first-order shelf.

    Positive tilt_db boosts bass / cuts highs; negative does the opposite.
    Capped at ±2 dB by the caller.
    """
    # #3661: use zero-phase sosfiltfilt so `low` and `high = result - low`
    # are time-aligned; causal sosfilt produced a first-order comb at the
    # 250 Hz crossover whenever the dynamics guard fired. Same fix template
    # as #3469 / #3470 / #3666.
    from scipy.signal import butter, sosfiltfilt
    result = audio.copy()
    tilt_db = max(-2.0, min(2.0, tilt_db))
    gain = 10.0 ** (abs(tilt_db) / 20.0)

    # Simple low-shelf at 250 Hz
    cutoff = min(250.0, sample_rate * 0.45)
    sos = butter(1, cutoff, btype='low', fs=sample_rate, output='sos')
    # Neither fallback of sosfiltfilt_safe is a tilt of nothing: too short to
    # split into bands, leave the buffer as it is (#5736).
    if not is_long_enough_for_sosfiltfilt(sos, result.shape[0]):
        return result
    low = sosfiltfilt(sos, result, axis=0)
    high = result - low

    if tilt_db > 0:
        result = low * gain + high / gain
    else:
        result = low / gain + high * gain

    # Preserve input dtype — sosfiltfilt upcasts float32 to float64
    return np.asarray(result, dtype=audio.dtype)