"""
Calibration of the similarity score's scale (#5923)

``similarity_score = 1 - distance / max_distance`` was computed with ``max_distance = 1.0``, the
distance between opposite extremes on every dimension, which no real pair approaches: unrelated
tracks sat near 0.4 distance and displayed as a ~60% match, so rank 1 and rank 20 looked alike.
The scale is now the typical distance between UNRELATED library tracks, measured at fit time: 0%
is an unrelated pair, 100% identical.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

import numpy as np

from ...utils.logging import debug, warning
from .distance import FingerprintDistance

DEFAULT_REFERENCE_DISTANCE = 1.0  # the uncalibrated scale: used until a fit has measured one
CALIBRATION_PERCENTILE = 95.0
CALIBRATION_SAMPLE = 300  # 300 tracks = ~45k pairs: a fraction of a second, whatever the library size
CALIBRATION_POOL = 5000  # the same bound find_similar puts on a full scan


def reference_distance_of(distance_calc: FingerprintDistance, vectors: np.ndarray) -> float:
    """The ``CALIBRATION_PERCENTILE`` of pairwise distances among normalised ``vectors`` (N x 25)."""
    pair_distances = [
        distance_calc.calculate_batch(vectors[i], vectors[i + 1:])
        for i in range(len(vectors) - 1)
    ]
    distances = np.concatenate(pair_distances) if pair_distances else np.empty(0)
    distances = distances[np.isfinite(distances)]
    if distances.size == 0:
        return DEFAULT_REFERENCE_DISTANCE
    reference = float(np.percentile(distances, CALIBRATION_PERCENTILE))
    return reference if reference > 1e-6 else DEFAULT_REFERENCE_DISTANCE


def calibrate_reference_distance(
    repository: Any, normalizer: Any, distance_calc: FingerprintDistance
) -> float:
    """Measure the reference distance from a random sample of the library; never raises."""
    try:
        fingerprints = repository.get_all(limit=CALIBRATION_POOL)
        if len(fingerprints) < 2:
            return DEFAULT_REFERENCE_DISTANCE
        rng = np.random.default_rng(0)  # fixed: the same library calibrates identically
        picked = rng.permutation(len(fingerprints))[:CALIBRATION_SAMPLE]
        vectors = np.array([normalizer.normalize(fingerprints[i].to_vector()) for i in picked])
        reference = reference_distance_of(distance_calc, vectors)
        debug(f"Similarity reference distance: {reference:.3f} ({len(vectors)} tracks sampled)")
        return reference
    except Exception as exc:
        warning(f"Similarity calibration failed, keeping the uncalibrated scale: {exc}")
        return DEFAULT_REFERENCE_DISTANCE
