"""
Reference weighting for soft k-NN target derivation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

The weight policy behind ``derive_target``: a softmax over the k nearest
references, the listening-behaviour ``reference_weight`` (#3480), and the soft
tail past rank k (#5113, #5702).
"""

import math
from collections.abc import Iterable
from typing import Any

EPSILON = 1e-6

# The tail is only there to stop participation stepping to zero at rank k, so
# it may never carry more than this share of the final weights (#5702).
MAX_TAIL_MASS = 0.10

# Tail references are admitted until the rank taper falls below this floor.
_TAIL_TAPER_FLOOR = 0.05


def safe_get(obj: Any, key: str, default: float = 0.0) -> float:
    """Read a feature from a dict or ORM row."""
    if hasattr(obj, '__table__'):                # ORM row
        return float(getattr(obj, key, default))
    if hasattr(obj, 'get'):                      # dict
        v = obj.get(key, default)
        return float(v if v is not None else default)
    return float(getattr(obj, key, default))


def smooth_taper(rank_past_k: int, tau_ranks: float) -> float:
    """Exponential decay for a reference `rank_past_k` positions beyond the
    soft cutoff: exp(-rank / tau_ranks), floor at zero. #5113."""
    if tau_ranks <= 0:
        return 0.0
    return math.exp(-rank_past_k / tau_ranks)


def softmax_tau(distances: Iterable[float]) -> float:
    """Adaptive softmax temperature τ = mean(distances) + EPSILON."""
    dist_list = list(distances)
    if not dist_list:
        return EPSILON
    return sum(dist_list) / len(dist_list) + EPSILON


def softmax_weights(distances: Iterable[float]) -> list[float]:
    """softmax(-d / τ) with adaptive τ = mean(distances) + EPSILON.

    Adaptive τ makes the weighting scale-free: a tight cluster of nearby
    references and a loose scatter both produce well-distributed weights.
    Returns weights summing to 1.0.
    """
    dist_list = list(distances)
    if not dist_list:
        return []
    tau = softmax_tau(dist_list)
    # Subtract max for numerical stability before exp.
    neg_scaled = [-d / tau for d in dist_list]
    mx = max(neg_scaled)
    exps = [math.exp(x - mx) for x in neg_scaled]
    total = sum(exps)
    return [e / total for e in exps]


def apply_reference_weights(
    weights: list[float],
    nearest: list[tuple[float, Any]],
) -> list[float]:
    """Scale softmax weights by each reference's `reference_weight`, then
    renormalize back to summing to 1.0 (#3480 Layer 1).

    Falls back to the original (unscaled) softmax weights if every matched
    reference has reference_weight <= 0 — either genuinely unweighted (a
    reference the seeder hasn't run listening-behavior scoring on yet, e.g.
    freshly migrated rows default to 0.0) or nothing matched. Treating "no
    behavioral signal" as "suppress this reference" would collapse the
    target to zero instead of degrading gracefully to pure quality-based
    distance weighting.
    """
    ref_weights = [max(safe_get(ref, 'reference_weight', 0.0), 0.0) for _, ref in nearest]
    combined = [w * rw for w, rw in zip(weights, ref_weights)]
    total = sum(combined)
    if total <= EPSILON:
        return weights
    return [c / total for c in combined]


def soft_tail(
    tail: list[tuple[float, Any]],
    k: int,
    nearest_distances: list[float],
    nearest_weights: list[float],
) -> tuple[list[tuple[float, Any]], list[float]]:
    """Softmax-scale weights for the references just past rank k (#5113, #5702).

    Each tail reference continues the in-k softmax: it starts from the k-th
    neighbour's own softmax weight, decays by the same ``exp(-Δd / τ)`` the
    in-k weights obey, and is tapered by rank past k. The previous two-way
    ``softmax([d, d_k])`` was ~0.5 against an in-k average of 1/k, so the
    tail outweighed the nearest references it was meant to soften.

    Only ranks whose taper stays above a floor are admitted. The returned
    weights are pre-``reference_weight``: the caller scales tail and in-k
    members together so a suppressed (weight 0) reference stays suppressed on
    both sides of rank k.

    Returns:
        (admitted tail members, their softmax-scale weights)
    """
    if not tail or not nearest_distances:
        return [], []
    kth_distance = nearest_distances[-1]
    kth_weight = nearest_weights[-1]
    tau = softmax_tau(nearest_distances)
    members: list[tuple[float, Any]] = []
    weights: list[float] = []
    for rank, (d, ref) in enumerate(tail, start=1):
        taper = smooth_taper(rank, k / 4.0)
        if taper < _TAIL_TAPER_FLOOR:
            break
        members.append((d, ref))
        weights.append(kth_weight * math.exp(-(d - kth_distance) / tau) * taper)
    return members, weights


def cap_tail_mass(weights: list[float], n_in_k: int) -> list[float]:
    """Normalize ``weights`` so the tail beyond ``n_in_k`` holds at most
    ``MAX_TAIL_MASS`` of the total (#5702).

    The tail is scaled down, never cut, so a reference crossing rank k still
    changes weight continuously. If the in-k members carry no weight at all
    (every one suppressed) the tail is the only signal left and is kept.
    """
    in_k = sum(weights[:n_in_k])
    tail = sum(weights[n_in_k:])
    allowed = in_k * MAX_TAIL_MASS / (1.0 - MAX_TAIL_MASS)
    if in_k > EPSILON and tail > allowed:
        scale = allowed / tail
        weights = weights[:n_in_k] + [w * scale for w in weights[n_in_k:]]
    total = sum(weights)
    if total <= 0:
        return weights
    return [w / total for w in weights]
