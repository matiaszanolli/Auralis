"""The band shares and the bass/mid ratio read the same frames (#6341).

``compute_frequency_distribution`` dropped a trailing frame shorter than half an FFT
frame while the bass/mid ratio kept it, so two dimensions of one fingerprint described
different spans of the track. Both now iterate the same frames, tail rule included, and
the algorithm version moved so stored v14 ratios are recomputed.
"""

import numpy as np
import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.analysis.fingerprint.rust_fingerprint import compute_fingerprint_schema

SAMPLE_RATE = 22050
FRAME = 65536  # the band analyses' frame at this length: next power of two, capped at 65536
BAND_KEYS = ("sub_bass_pct", "bass_pct", "low_mid_pct", "mid_pct", "upper_mid_pct", "presence_pct", "air_pct")


def _tone(freq: float, samples: int, start: int = 0) -> np.ndarray:
    t = (np.arange(samples) + start) / SAMPLE_RATE
    return (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _fingerprint(mono: np.ndarray) -> dict[str, float]:
    return compute_fingerprint_schema(np.ascontiguousarray(mono, dtype=np.float32), SAMPLE_RATE, 1)


@pytest.fixture(scope="module")
def whole_frames() -> np.ndarray:
    """Thirteen whole frames of a mid tone (about 38.7 s)."""
    return _tone(1000.0, 13 * FRAME)


def test_a_tail_under_half_a_frame_moves_neither_the_band_shares_nor_the_ratio(whole_frames):
    base = _fingerprint(whole_frames)
    tailed = _fingerprint(np.concatenate([whole_frames, _tone(100.0, 1000, start=len(whole_frames))]))

    for key in (*BAND_KEYS, "bass_mid_ratio"):
        assert tailed[key] == pytest.approx(base[key], rel=1e-5, abs=1e-6), key


def test_a_tail_of_half_a_frame_or_more_moves_both(whole_frames):
    base = _fingerprint(whole_frames)
    tailed = _fingerprint(np.concatenate([whole_frames, _tone(100.0, 40000, start=len(whole_frames))]))

    assert tailed["bass_pct"] > base["bass_pct"]
    assert tailed["bass_mid_ratio"] > base["bass_mid_ratio"]


def test_stored_v14_rows_are_recomputed():
    assert FINGERPRINT_ALGORITHM_VERSION >= 15
