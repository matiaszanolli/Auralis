"""
Regression test for #3741 — genre classifier weight determinism.

Before the fix, `initialize_genre_weights` sampled from the un-seeded
module-level `np.random` state, so every `RuleBasedGenreClassifier`
instance and every process got different weights. That cascaded into
`EQProcessor._apply_content_adjustments` where the predicted genre
scales `bass_boost`, `treble_boost`, `mid_boost` by up to 30%, so the
same audio mastered twice diverged audibly. Determinism here is a
precondition for the "same file → same fingerprint / same master"
invariant the rest of the engine depends on.

The fix seeds with a fixed RNG (`np.random.default_rng(0x6A52A1E5)`).
"""

from __future__ import annotations

import numpy as np

from auralis.analysis.ml.genre_classifier import RuleBasedGenreClassifier
from auralis.analysis.ml.genre_weights import initialize_genre_weights


GENRES = [
    "electronic", "classical", "rock", "jazz", "hip_hop",
    "ambient", "metal", "acoustic", "pop", "country",
]


def test_initialize_genre_weights_is_deterministic_across_calls() -> None:
    a = initialize_genre_weights(GENRES)
    b = initialize_genre_weights(GENRES)
    assert a == b, "Two calls produced different weight dicts"


def test_classifier_instances_share_identical_weights() -> None:
    c1 = RuleBasedGenreClassifier()
    c2 = RuleBasedGenreClassifier()
    # Compare every weight slot across the two instances.
    assert set(c1.weights.keys()) == set(c2.weights.keys())
    for genre in c1.weights:
        assert c1.weights[genre] == c2.weights[genre], (
            f"Genre '{genre}' has divergent weights across instances"
        )


def test_global_numpy_rng_not_consumed_by_initializer() -> None:
    """The fix must not advance the global `np.random` state; otherwise
    code that relies on it elsewhere would be affected by classifier
    construction order (a subtle action-at-a-distance hazard)."""
    np.random.seed(42)
    a = np.random.normal()
    np.random.seed(42)
    _ = initialize_genre_weights(GENRES)
    b = np.random.normal()
    assert a == b, (
        "initialize_genre_weights consumed entropy from the global "
        "np.random state — must use a local Generator instead"
    )
