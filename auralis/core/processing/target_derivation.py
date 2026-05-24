"""
Soft k-NN Mastering Target Derivation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Given a source fingerprint and a cloud of "well-mastered" references, derive
a continuous target spectral shape for the EQ stage. This is the heart of
content-aware mastering: instead of classifying the source into a genre
bucket and applying a preset, we interpolate continuously across the
reference manifold.

How it works (one process() call):

  1. Compute distance from source to every reference in the cloud, using only
     "character" features (tempo, rhythm, dynamics, stereo) — explicitly
     EXCLUDING the spectral fields we want to target. This keeps the k-NN
     from snapping to references that already sound like the source and
     leaves room for actual correction.

  2. Pick the k nearest references.

  3. Compute soft weights via softmax(-d/τ) where τ is the mean of those
     k distances. This is scale-free — works on any library.

  4. Return a weighted average of the references' spectral fields as the
     target. Each band is a continuous interpolation across the manifold.

No genre labels. No bucketing. A track in the middle of two clusters gets
an interpolated target in the middle of those clusters' shapes.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Mapping

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature splits (declared once; consumers must NOT add their own)
# ---------------------------------------------------------------------------

# Features used to compute distance (find "what is this source LIKE").
# Deliberately excludes anything we want to TARGET so the k-NN doesn't
# match like-to-like on the very dimensions we're trying to correct.
DISTANCE_FEATURES: tuple[str, ...] = (
    'tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio',
    'harmonic_ratio', 'pitch_stability', 'chroma_energy',
    'dynamic_range_variation', 'loudness_variation_std', 'peak_consistency',
    'stereo_width', 'phase_correlation',
    'crest_db',
)

# Features extracted from the matched references to form the EQ target.
# These ARE the things we want to drive the source toward.
TARGET_FEATURES: tuple[str, ...] = (
    'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
    'upper_mid_pct', 'presence_pct', 'air_pct',
    'spectral_centroid', 'spectral_rolloff', 'bass_mid_ratio',
)


# ---------------------------------------------------------------------------
# Stats (z-score normalization for distance computation)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DistanceStats:
    """Per-feature mean and std from the reference cloud.

    Used to z-score each feature so they contribute on equal footing to the
    Euclidean distance regardless of native unit (e.g. tempo_bpm spans
    40-200 while phase_correlation spans 0-1).
    """

    means: Mapping[str, float]
    stds: Mapping[str, float]

    @classmethod
    def from_references(cls, references: list[Any]) -> DistanceStats:
        """Fit z-score stats from the reference cloud.

        Standard deviations below EPSILON are clipped to EPSILON to avoid
        divide-by-zero when a feature is constant across the cloud.
        """
        if not references:
            return cls(means={f: 0.0 for f in DISTANCE_FEATURES},
                       stds={f: 1.0 for f in DISTANCE_FEATURES})

        means: dict[str, float] = {}
        stds: dict[str, float] = {}
        n = float(len(references))
        for feat in DISTANCE_FEATURES:
            values = [_safe_get(ref, feat, 0.0) for ref in references]
            m = sum(values) / n
            var = sum((v - m) ** 2 for v in values) / n
            std = math.sqrt(var)
            means[feat] = m
            stds[feat] = max(std, _EPSILON)
        return cls(means=means, stds=stds)


# ---------------------------------------------------------------------------
# Target derivation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TargetDerivation:
    """Result of derive_target. Includes diagnostics for debugging/UI."""

    target: dict[str, float]                    # Target value per TARGET_FEATURE
    n_matched: int                              # How many references actually used
    weights: tuple[float, ...]                  # Soft weights of those refs (sums to 1.0)
    top_ref_ids: tuple[int, ...]                # track_ids of the matched refs (for debug)


def derive_target(
    source: Any,
    references: list[Any],
    stats: DistanceStats,
    *,
    k: int = 10,
) -> TargetDerivation | None:
    """Derive a continuous target spectrum from soft k-NN over the reference cloud.

    Args:
        source: Source fingerprint (ORM row or dict).
        references: Reference cloud (list of fingerprints).
        stats: Per-feature normalization stats (from DistanceStats.from_references).
        k: How many nearest neighbors to weight in the target.

    Returns:
        TargetDerivation, or None if the cloud is empty (caller falls back).
    """
    if not references:
        return None

    distances = [(_z_distance(source, ref, stats), ref) for ref in references]
    distances.sort(key=lambda t: t[0])
    nearest = distances[:k] if k < len(distances) else distances

    weights = _softmax_weights(d for d, _ in nearest)

    target: dict[str, float] = {}
    for feat in TARGET_FEATURES:
        target[feat] = sum(
            w * _safe_get(ref, feat, 0.0)
            for w, (_, ref) in zip(weights, nearest)
        )

    return TargetDerivation(
        target=target,
        n_matched=len(nearest),
        weights=tuple(weights),
        top_ref_ids=tuple(int(_safe_get(ref, 'track_id', -1)) for _, ref in nearest),
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

_EPSILON = 1e-6


def _safe_get(obj: Any, key: str, default: float = 0.0) -> float:
    """Read a feature from a dict or ORM row."""
    if hasattr(obj, '__table__'):                # ORM row
        return float(getattr(obj, key, default))
    if hasattr(obj, 'get'):                      # dict
        v = obj.get(key, default)
        return float(v if v is not None else default)
    return float(getattr(obj, key, default))


def _z_distance(a: Any, b: Any, stats: DistanceStats) -> float:
    """Z-score-normalized Euclidean distance over DISTANCE_FEATURES."""
    acc = 0.0
    for feat in DISTANCE_FEATURES:
        std = stats.stds[feat]
        mean = stats.means[feat]
        za = (_safe_get(a, feat, mean) - mean) / std
        zb = (_safe_get(b, feat, mean) - mean) / std
        acc += (za - zb) ** 2
    return math.sqrt(acc)


def _softmax_weights(distances) -> list[float]:
    """softmax(-d / τ) with adaptive τ = mean(distances) + EPSILON.

    Adaptive τ makes the weighting scale-free: a tight cluster of nearby
    references and a loose scatter both produce well-distributed weights.
    Returns weights summing to 1.0.
    """
    dist_list = list(distances)
    if not dist_list:
        return []
    tau = sum(dist_list) / len(dist_list) + _EPSILON
    # Subtract max for numerical stability before exp.
    neg_scaled = [-d / tau for d in dist_list]
    mx = max(neg_scaled)
    exps = [math.exp(x - mx) for x in neg_scaled]
    total = sum(exps)
    return [e / total for e in exps]


__all__ = [
    "DISTANCE_FEATURES",
    "TARGET_FEATURES",
    "DistanceStats",
    "TargetDerivation",
    "derive_target",
]
