"""
Regression: the level matcher starts at the reference level, not at zero (#5707)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``current_target_rms`` began at 0.0 and eased toward ``reference_rms`` at
alpha=0.01 per chunk while ``gain = current_target_rms / current_rms``, so the
first chunks played at about -34 dB and the track swelled in over ~7 s.
"""

import numpy as np

from auralis.player.config import PlayerConfig
from auralis.player.realtime.level_matcher import RealtimeLevelMatcher

CHUNK = 1024


def _noise(seed: int, scale: float = 0.2, frames: int = CHUNK * 8) -> np.ndarray:
    return (np.random.default_rng(seed).standard_normal((frames, 2)) * scale).astype(np.float32)


def _rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))


def _db(ratio: float) -> float:
    return 20 * np.log10(ratio)


def _matcher(reference: np.ndarray) -> RealtimeLevelMatcher:
    matcher = RealtimeLevelMatcher(PlayerConfig())
    matcher.set_reference_audio(reference)
    return matcher


def test_first_chunk_of_equal_rms_material_is_near_unity():
    signal = _noise(1)
    matcher = _matcher(signal)

    out = matcher.process(signal[:CHUNK])

    assert abs(_db(_rms(out) / _rms(signal[:CHUNK]))) < 1.0


def test_level_stays_flat_across_the_following_chunks():
    signal = _noise(2)
    matcher = _matcher(signal)

    ratios = [
        _db(_rms(matcher.process(signal[i:i + CHUNK])) / _rms(signal[i:i + CHUNK]))
        for i in range(0, len(signal), CHUNK)
    ]

    assert max(abs(r) for r in ratios) < 1.0


def test_reset_then_a_new_reference_starts_from_the_new_level():
    matcher = _matcher(_noise(3, scale=0.2))
    matcher.process(_noise(3, scale=0.2)[:CHUNK])

    matcher.reset()
    assert matcher.current_target_rms == 0.0
    quiet = _noise(4, scale=0.05)
    matcher.set_reference_audio(quiet)

    assert abs(matcher.current_target_rms - _rms(quiet)) < 1e-6
    out = matcher.process(quiet[:CHUNK])
    assert abs(_db(_rms(out) / _rms(quiet[:CHUNK]))) < 1.0


def test_a_reference_change_mid_session_still_glides():
    matcher = _matcher(_noise(5, scale=0.2))
    seeded = matcher.current_target_rms

    matcher.set_reference_audio(_noise(6, scale=0.02))

    assert matcher.current_target_rms == seeded  # moves only as chunks are processed
