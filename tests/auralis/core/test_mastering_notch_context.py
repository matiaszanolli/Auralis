"""Tests for frequency-aware resonance-notch contextualization."""

import pytest

from auralis.core.dsp import Notch
from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.mastering_notch_context import contextualize_notches


def _fingerprint() -> dict[str, float]:
    return {
        'sub_bass_pct': 0.087,
        'bass_pct': 0.460,
        'low_mid_pct': 0.136,
        'mid_pct': 0.171,
        'upper_mid_pct': 0.055,
        'presence_pct': 0.015,
        'air_pct': 0.001,
    }


def test_bass_harmonic_notch_is_shallower_and_narrower():
    result = contextualize_notches(
        [Notch(freq_hz=186.0, depth_db=-3.0, q=6.0)],
        _fingerprint(),
        SimpleMasteringConfig(),
    )

    assert len(result) == 1
    assert -0.6 < result[0].depth_db < -0.3
    assert result[0].q > 10.0


def test_midrange_notch_is_smoothly_depth_compressed():
    result = contextualize_notches(
        [Notch(freq_hz=700.0, depth_db=-2.0, q=6.0)],
        _fingerprint(),
        SimpleMasteringConfig(),
    )

    assert len(result) == 1
    assert result[0].depth_db == pytest.approx(-1.58, abs=0.03)
    assert 6.0 <= result[0].q < 6.01


def test_clustered_notches_share_a_smooth_band_budget():
    result = contextualize_notches(
        [
            Notch(freq_hz=590.0, depth_db=-4.0, q=6.0),
            Notch(freq_hz=745.0, depth_db=-4.0, q=6.0),
            Notch(freq_hz=880.0, depth_db=-4.0, q=6.0),
        ],
        _fingerprint(),
        SimpleMasteringConfig(),
    )

    assert len(result) == 3
    assert all(-1.4 < notch.depth_db < -1.1 for notch in result)
    assert sum(abs(notch.depth_db) for notch in result) < 4.0
