"""LoudnessMeter's loudness range is EBU Tech 3342 LRA (#5741).

It used to be the 10th-95th percentile spread of 400 ms blocks gated 10 LU
below the integrated level, which reads several LU high on rhythmic material
(2.71 LU vs ffmpeg's 0.1 LU for a stationary 2 Hz pulse) and on stepped
material. LRA is the spread of 3 s short-term loudness, gated 20 LU down.
"""

import numpy as np
import pytest

from auralis.analysis.loudness_meter import LoudnessMeter
from auralis.analysis.loudness_range import loudness_range_lu

SR = 44100


def _measure(audio: np.ndarray, chunk_sec: float = 0.4):
    meter = LoudnessMeter(SR)
    size = int(chunk_sec * SR)
    for i in range(0, len(audio), size):
        chunk = audio[i:i + size]
        if len(chunk) >= size // 2:
            meter.measure_chunk(chunk)
    return meter.finalize_measurement()


def _noise(seconds: float, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal((int(seconds * SR), 2)) * 0.1


def test_a_stationary_pulse_envelope_has_almost_no_loudness_range():
    audio = _noise(90.0)
    t = np.arange(len(audio)) / SR
    audio *= (0.5 + 0.5 * np.sin(2 * np.pi * 2.0 * t))[:, None] ** 0.5

    assert _measure(audio).loudness_range < 0.5


def test_eight_db_steps_every_fifteen_seconds_give_an_eight_lu_range():
    sections = [_noise(15.0, seed=i) * (10 ** (-8.0 * (i % 2) / 20)) for i in range(6)]

    assert _measure(np.concatenate(sections)).loudness_range == pytest.approx(8.0, abs=0.5)


def test_integrated_loudness_keeps_its_bs1770_reference_value():
    """BS.1770: a full-scale 997 Hz sine on both channels reads 0 LUFS."""
    t = np.arange(10 * SR) / SR
    sine = np.sin(2 * np.pi * 997.0 * t)

    assert _measure(np.stack([sine, sine], axis=1)).integrated_lufs == pytest.approx(0.0, abs=0.3)


def test_blocks_of_other_lengths_compose_into_the_same_windows():
    audio = _noise(60.0) * (1.0 + 0.8 * (np.arange(60 * SR) // (10 * SR) % 2))[:, None]

    assert _measure(audio, 0.4).loudness_range == pytest.approx(
        _measure(audio, 0.8).loudness_range, abs=0.3
    )


def test_a_measurement_shorter_than_one_window_has_no_range():
    assert _measure(_noise(2.0)).loudness_range == 0.0
    assert loudness_range_lu([], [], SR) == 0.0


def test_silence_has_no_range():
    assert _measure(np.zeros((10 * SR, 2))).loudness_range == 0.0
