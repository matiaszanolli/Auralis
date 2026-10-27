"""Regression tests: the soft k-NN tail must not outweigh the k nearest (#5702)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#5113 re-admitted every reference past rank k with
``softmax([d, d_k])[0] * taper``. That two-way softmax is ~0.5 while the in-k
weights (a k-way softmax) average 1/k, so the beyond-k references carried
about half of the total mass and the "k nearest" target slid toward the cloud
mean. The tail also skipped ``reference_weight``, so references the seeder
scored 0 leaked back in beyond rank k.
"""

from __future__ import annotations

import numpy as np
import pytest

from auralis.core.processing.target_derivation import (
    DISTANCE_FEATURES,
    TARGET_FEATURES,
    DistanceStats,
    derive_target,
)

K = 10


def _random_cloud(n: int, rng: np.random.Generator, **extra: float) -> list[dict[str, float]]:
    return [
        {
            'track_id': i,
            **{f: float(rng.normal()) for f in DISTANCE_FEATURES},
            **{f: float(rng.uniform(0.0, 1.0)) for f in TARGET_FEATURES},
            'reference_weight': 1.0,
            **extra,
        }
        for i in range(n)
    ]


def _source(rng: np.random.Generator) -> dict[str, float]:
    return {f: float(rng.normal()) for f in DISTANCE_FEATURES}


class TestTailMass:
    @pytest.mark.parametrize("n_refs", [15, 30, 100])
    def test_in_k_mass_is_at_least_ninety_percent(self, n_refs):
        for seed in range(25):
            rng = np.random.default_rng(seed)
            refs = _random_cloud(n_refs, rng)
            stats = DistanceStats.from_references(refs)

            result = derive_target(_source(rng), refs, stats, k=K)

            assert result is not None
            assert sum(result.weights[:K]) >= 0.9 - 1e-9, (
                f"N={n_refs} seed={seed}: in-k mass {sum(result.weights[:K]):.3f}"
            )
            assert sum(result.weights) == pytest.approx(1.0)

    def test_tail_is_still_admitted_and_decays_with_rank(self):
        """The #5113 goal survives: references past rank k are not cut to zero."""
        rng = np.random.default_rng(7)
        refs = _random_cloud(30, rng)
        stats = DistanceStats.from_references(refs)

        result = derive_target(_source(rng), refs, stats, k=K)

        assert result is not None
        assert result.n_matched > K
        tail = result.weights[K:]
        assert all(w > 0.0 for w in tail)
        assert list(tail) == sorted(tail, reverse=True)
        assert max(tail) <= min(result.weights[:K]) + 1e-12

    def test_small_cloud_has_no_tail(self):
        rng = np.random.default_rng(3)
        refs = _random_cloud(K, rng)
        stats = DistanceStats.from_references(refs)

        result = derive_target(_source(rng), refs, stats, k=K)

        assert result is not None
        assert result.n_matched == K


class TestReferenceWeightApplies:
    def test_suppressed_references_carry_no_weight_in_or_beyond_k(self):
        rng = np.random.default_rng(11)
        refs = _random_cloud(30, rng)
        suppressed = set(rng.choice(30, size=20, replace=False).tolist())
        for ref in refs:
            if ref['track_id'] in suppressed:
                ref['reference_weight'] = 0.0
        stats = DistanceStats.from_references(refs)

        result = derive_target(_source(rng), refs, stats, k=K)

        assert result is not None
        zero_mass = sum(
            w for w, tid in zip(result.weights, result.top_ref_ids) if tid in suppressed
        )
        assert zero_mass < 0.01
        assert sum(result.weights) == pytest.approx(1.0)

    def test_all_zero_reference_weights_still_fall_back_to_distance_weighting(self):
        rng = np.random.default_rng(13)
        refs = _random_cloud(30, rng, reference_weight=0.0)
        stats = DistanceStats.from_references(refs)

        result = derive_target(_source(rng), refs, stats, k=K)

        assert result is not None
        assert sum(result.weights) == pytest.approx(1.0)
        assert sum(result.weights[:K]) >= 0.9 - 1e-9

    def test_weights_off_ignores_reference_weight_but_keeps_the_cap(self):
        rng = np.random.default_rng(17)
        refs = _random_cloud(30, rng)
        for ref in refs[:15]:
            ref['reference_weight'] = 0.0
        stats = DistanceStats.from_references(refs)

        result = derive_target(_source(rng), refs, stats, k=K, use_reference_weights=False)

        assert result is not None
        assert sum(result.weights[:K]) >= 0.9 - 1e-9


class TestContinuityAcrossRankK:
    def test_target_does_not_jump_when_two_references_swap_rank_k(self):
        """Move the source across the point where reference A and B trade
        places at rank K: the target must change by a small, bounded amount
        (the original #5113 goal), not by a whole reference's weight."""
        # One-dimensional cloud on tempo: references at 100, 101, 102, ...
        refs = []
        for i in range(25):
            refs.append({
                'track_id': i,
                **{f: 0.0 for f in DISTANCE_FEATURES},
                **{f: 0.0 for f in TARGET_FEATURES},
                'tempo_bpm': 100.0 + i,
                'air_pct': 1.0 if i == K else 0.0,   # one reference marks the boundary
                'reference_weight': 1.0,
            })
        stats = DistanceStats.from_references(refs)

        def air(source_tempo: float) -> float:
            src = {f: 0.0 for f in DISTANCE_FEATURES}
            src['tempo_bpm'] = source_tempo
            result = derive_target(src, refs, stats, k=K)
            assert result is not None
            return result.target['air_pct']

        # Reference #K is rank K+1 (tail) for a source at 100.0 and enters
        # the k nearest once the source has moved past the K/2 midpoint
        # with its neighbour; sweep finely and bound the largest step.
        positions = np.linspace(100.0, 110.0, 4001)
        values = np.array([air(float(p)) for p in positions])

        assert np.abs(np.diff(values)).max() < 0.01
