"""compute_fingerprint's tempo_bpm survives accents and aperiodic input (#5742).

The onset-envelope autocorrelation was an unnormalised argmax: an accented
120/140/180 BPM click track reported 60/70/60 and white noise the shortest lag
(~199 BPM). Rust unit tests cover the estimator; these pin the dimension as the
Python side stores it, and the version bump that makes old values recompute.
"""

import numpy as np
import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION

auralis_dsp = pytest.importorskip(
    "auralis_dsp",
    reason="Rust DSP module not built — run `cd vendor/auralis-dsp && maturin develop`",
)

SR = 44100


def _clicks(bpm: float, seconds: float = 30.0, accent_every: int | None = None) -> np.ndarray:
    audio = np.zeros(int(seconds * SR), dtype=np.float32)
    period = int(SR * 60.0 / bpm)
    decay = np.linspace(1.0, 0.0, 64, dtype=np.float32)
    for beat, start in enumerate(range(0, len(audio) - 64, period)):
        level = 0.9 if accent_every is None or beat % accent_every == 0 else 0.3
        audio[start:start + 64] = decay * level
    return audio


def _tempo(audio: np.ndarray) -> float:
    return auralis_dsp.compute_fingerprint(audio, SR, 1)["tempo_bpm"]


@pytest.mark.parametrize("bpm", [120.0, 140.0, 180.0])
def test_accented_click_tracks_report_the_beat_not_half_tempo(bpm):
    assert _tempo(_clicks(bpm, accent_every=4)) == pytest.approx(bpm, abs=2.0)


@pytest.mark.parametrize("bpm", [90.0, 100.0, 150.0])
def test_plain_click_tracks_keep_their_estimate(bpm):
    assert _tempo(_clicks(bpm)) == pytest.approx(bpm, abs=2.0)


def test_white_noise_is_not_reported_as_the_shortest_lag():
    noise = (np.random.default_rng(7).standard_normal(SR * 30) * 0.1).astype(np.float32)

    assert abs(_tempo(noise) - 200.0) > 1.0


def test_the_algorithm_version_was_bumped_past_the_old_tempo():
    assert FINGERPRINT_ALGORITHM_VERSION >= 11
