"""A level-smoothing boost never pushes a chunk past the limiter ceiling (#5558).

LevelManager boosts a chunk quieter than its predecessor after the brick-wall limiter, with no peak
check: chunks peaking at the -0.3 dBFS ceiling could leave near 1.7 and be streamed as float32.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.level_manager import LevelManager  # noqa: E402
from core.level_peak_guard import PEAK_CEILING, peak_safe_gain_db  # noqa: E402

SR = 44100


def _chunk(rms_db: float, peak: float = 0.966, seconds: float = 2.0) -> np.ndarray:
    """High-crest chunk: mostly low-level noise with a few samples at `peak`."""
    n = int(SR * seconds)
    rng = np.random.default_rng(1)
    body = rng.standard_normal((n, 2)).astype(np.float32)
    body *= 10 ** (rms_db / 20) / float(np.sqrt(np.mean(body ** 2)))
    body[::SR // 2] = peak
    return body


def test_the_audit_scenario_stays_under_the_ceiling():
    manager = LevelManager()
    loud = _chunk(-12.0)
    quiet = _chunk(-22.0)  # 10 dB quieter, same peak: the old boost was ~+8.4 dB -> peak ~1.7

    manager.smooth_transition(loud, 0, sample_rate=SR)
    adjusted, gain_db, applied = manager.smooth_transition(quiet, 1, sample_rate=SR)

    assert float(np.max(np.abs(adjusted))) <= PEAK_CEILING + 1e-4
    assert gain_db <= 0.01  # no headroom: the boost is withheld, not clipped


def test_a_boost_with_headroom_still_applies():
    manager = LevelManager()
    loud = _chunk(-12.0, peak=0.9)
    quiet = _chunk(-22.0, peak=0.1)  # plenty of headroom

    manager.smooth_transition(loud, 0, sample_rate=SR)
    adjusted, gain_db, applied = manager.smooth_transition(quiet, 1, sample_rate=SR)

    assert applied and gain_db > 3.0
    assert float(np.max(np.abs(adjusted))) <= PEAK_CEILING + 1e-4


@pytest.mark.parametrize("gain_db", [-6.0, 0.0])
def test_attenuation_and_unity_are_untouched(gain_db):
    assert peak_safe_gain_db(gain_db, _chunk(-10.0)) == gain_db


def test_a_silent_chunk_is_not_capped():
    assert peak_safe_gain_db(6.0, np.zeros((100, 2), dtype=np.float32)) == 6.0
