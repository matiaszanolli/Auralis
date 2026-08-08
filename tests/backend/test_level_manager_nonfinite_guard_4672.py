"""
Regression tests for LevelManager NaN/Inf guard (#4672).

calculate_rms() had no finite guard of its own: np.sqrt(np.mean(audio**2))
on a NaN chunk returns NaN, which then flowed into rms_history via
smooth_transition(). NaN comparisons are always False, so
`abs(level_diff_db) > self.max_level_change_db` silently takes the
no-adjustment branch forever after — smoothing stops applying for every
subsequent chunk in the track, with no error.

calculate_rms() must reject non-finite input and fall back to the last
known-good level instead, keeping rms_history entirely finite.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.level_manager import LevelManager, SILENCE_FLOOR_DB


SR = 44100


def _loud(n=SR, ch=2, amp=0.5):
    return np.ones((n, ch), dtype=np.float32) * amp


def _nan_chunk(n=SR, ch=2):
    return np.full((n, ch), np.nan, dtype=np.float32)


def _inf_chunk(n=SR, ch=2):
    return np.full((n, ch), np.inf, dtype=np.float32)


def test_calculate_rms_on_nan_falls_back_to_last_known_level():
    lm = LevelManager()
    lm.rms_history.append(-12.0)
    rms = lm.calculate_rms(_nan_chunk())
    assert rms == -12.0
    assert np.isfinite(rms)


def test_calculate_rms_on_inf_falls_back_to_last_known_level():
    lm = LevelManager()
    lm.rms_history.append(-18.0)
    rms = lm.calculate_rms(_inf_chunk())
    assert np.isfinite(rms)
    assert rms == -18.0


def test_calculate_rms_on_nan_with_no_history_uses_silence_floor():
    lm = LevelManager()
    rms = lm.calculate_rms(_nan_chunk())
    assert rms == SILENCE_FLOOR_DB


def test_smooth_transition_never_poisons_rms_history_with_nan():
    """End-to-end: a NaN chunk mid-track must not leave a NaN in
    rms_history, and smoothing must keep working for the chunk after it."""
    lm = LevelManager()

    # Baseline chunk.
    lm.smooth_transition(_loud(amp=0.5), 0, sample_rate=SR)
    assert all(np.isfinite(v) for v in lm.rms_history)

    # Poisoned chunk.
    lm.smooth_transition(_nan_chunk(), 1, sample_rate=SR)
    assert all(np.isfinite(v) for v in lm.rms_history), (
        f"NaN leaked into rms_history: {list(lm.rms_history)}"
    )

    # A real level jump after the poisoned chunk must still trigger smoothing
    # — proves the guard didn't just avoid a crash, it kept the mechanism
    # functional for subsequent chunks.
    out, gain_db, adjusted = lm.smooth_transition(_loud(amp=0.02), 2, sample_rate=SR)
    assert adjusted, "smoothing must still trigger after a poisoned chunk"
    assert np.isfinite(gain_db)
    assert np.all(np.isfinite(out))
