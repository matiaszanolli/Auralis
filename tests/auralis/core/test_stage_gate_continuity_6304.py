"""Stage minimum-effect gates are not audible cliffs (#6304).

The transient shaper ran its bass band only `if bass_pct >= 0.05` (low-mid the same), so 0.0499 -> 0.0501 went
from absent to full strength, and the transient shaper / air / clarity / presence / warmth stages bypassed below a
0.3-0.5 dB computed boost, a jump of the same size. The band boost now fades in across 0.04-0.06 and the bypass
floor is MIN_AUDIBLE_BOOST_DB (0.05 dB).
"""

import numpy as np
import pytest

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.stages import MIN_AUDIBLE_BOOST_DB, transient_shaper

SR = 44100


def _boosts(monkeypatch, bass_pct, low_mid_pct=0.3, crest_db=6.0, intensity=1.0):
    """The attack boosts the shaper hands to the DSP, bass band first."""
    seen: list[tuple[float, float]] = []

    def fake_apply(audio, sample_rate, band_low_hz, band_high_hz, attack_boost_db, **_):
        seen.append((band_low_hz, attack_boost_db))
        return audio

    monkeypatch.setattr(transient_shaper.TransientShaper, "apply", staticmethod(fake_apply))
    audio = np.zeros((SR // 4, 2), dtype=np.float32)
    transient_shaper.apply(audio, bass_pct, low_mid_pct, crest_db, intensity, SR, False, SimpleMasteringConfig())
    return seen


def _bass_boost(monkeypatch, bass_pct):
    config = SimpleMasteringConfig()
    boosts = [b for low, b in _boosts(monkeypatch, bass_pct) if low == config.TRANSIENT_BASS_LOW_HZ]
    return boosts[0] if boosts else 0.0


def test_the_bass_band_boost_has_no_step_at_five_percent_bass(monkeypatch):
    below = _bass_boost(monkeypatch, 0.0499)
    above = _bass_boost(monkeypatch, 0.0501)

    assert abs(above - below) < 0.15  # the knee slope over 0.0002 of bass share; was the whole ~2.5 dB boost switching on


def test_the_boost_is_off_without_bass_and_full_with_it(monkeypatch):
    assert _bass_boost(monkeypatch, 0.0) == 0.0
    full = _bass_boost(monkeypatch, 0.3)
    assert full > 0.5
    assert _bass_boost(monkeypatch, 0.05) == pytest.approx(full / 2, rel=0.05)  # the knee's midpoint


def test_bypass_floor_is_no_longer_the_old_half_db():
    assert MIN_AUDIBLE_BOOST_DB <= 0.1
