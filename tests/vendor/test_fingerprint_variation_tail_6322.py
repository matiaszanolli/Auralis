"""A trailing partial 1 s frame must not move the variation dimensions (#6322).

`loudness_variation_std`, `dynamic_range_variation` and `peak_consistency` are
standard deviations / coefficients of variation over 1 s frames. The final short
slice used to count as much as a whole second, so on a track under ~90 s one
extra sample doubled `dynamic_range_variation`, and the same audio read at 44.1
and 48 kHz disagreed. Only whole frames are scored now, and the algorithm
version moved so stored v11 rows are recomputed.
"""

import numpy as np
import pytest

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.analysis.fingerprint.rust_fingerprint import compute_fingerprint_schema

VARIATION_KEYS = ("dynamic_range_variation", "loudness_variation_std", "peak_consistency")
SAMPLE_RATE = 44100


def _music_like(seconds: int) -> np.ndarray:
    """Amplitude-modulated tone plus noise, so frames genuinely differ a little."""
    rng = np.random.default_rng(0)
    t = np.arange(SAMPLE_RATE * seconds) / SAMPLE_RATE
    mono = 0.4 * np.sin(2 * np.pi * 220 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.3 * t))
    mono = (mono + 0.02 * rng.standard_normal(t.size)).astype(np.float32)
    return np.column_stack([mono, mono])


def _fingerprint(stereo: np.ndarray) -> dict[str, float]:
    return compute_fingerprint_schema(np.ascontiguousarray(stereo.ravel()), SAMPLE_RATE, 2)


@pytest.fixture(scope="module")
def base_fingerprint() -> dict[str, float]:
    return _fingerprint(_music_like(20))


@pytest.mark.parametrize(
    "tail_samples",
    [1, 7, 20000],
    ids=["one-sample", "seven-samples", "under-half-second"],
)
def test_a_partial_trailing_frame_leaves_the_variation_dimensions_unchanged(base_fingerprint, tail_samples):
    stereo = _music_like(20)
    tail = np.full((tail_samples, 2), 0.9, dtype=np.float32)
    padded = _fingerprint(np.vstack([stereo, tail]))

    for key in VARIATION_KEYS:
        assert padded[key] == pytest.approx(base_fingerprint[key], rel=1e-6), key


def test_stored_v11_rows_are_recomputed():
    assert FINGERPRINT_ALGORITHM_VERSION >= 12
