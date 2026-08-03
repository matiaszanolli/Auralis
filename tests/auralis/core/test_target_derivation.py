"""
Tests for the soft k-NN mastering target derivation.

The module is pure math (no DB, no audio), so all tests use plain dicts as
fingerprints. Verifies the distance/target feature splits, z-score stats
fitting, soft-weight properties, and target interpolation across the cloud.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from auralis.core.processing.target_derivation import (
    DISTANCE_FEATURES,
    TARGET_FEATURES,
    DistanceStats,
    derive_target,
)


# ---------------------------------------------------------------------------
# Fingerprint stub builder
# ---------------------------------------------------------------------------

def _fp(*, track_id: int = 0, **overrides: Any) -> dict[str, float]:
    """Build a fingerprint dict with reasonable defaults for every feature."""
    base = {
        # Distance features
        'tempo_bpm': 120.0, 'rhythm_stability': 0.7, 'transient_density': 0.4,
        'silence_ratio': 0.02, 'harmonic_ratio': 0.65, 'pitch_stability': 0.7,
        'chroma_energy': 0.55, 'dynamic_range_variation': 0.3,
        'loudness_variation_std': 1.5, 'peak_consistency': 0.7,
        'stereo_width': 0.4, 'phase_correlation': 0.8, 'crest_db': 12.0,
        # Target features
        'sub_bass_pct': 0.05, 'bass_pct': 0.20, 'low_mid_pct': 0.15,
        'mid_pct': 0.25, 'upper_mid_pct': 0.15, 'presence_pct': 0.10,
        'air_pct': 0.10, 'spectral_centroid': 0.4, 'spectral_rolloff': 0.5,
        'bass_mid_ratio': 0.0,
        'track_id': track_id,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Feature splits — invariant; must not silently drift
# ---------------------------------------------------------------------------

def test_distance_and_target_features_are_disjoint():
    """A feature should never be both a query and a target — that would
    encourage the k-NN to lock onto sources already similar to the target,
    leaving no room for correction."""
    assert not (set(DISTANCE_FEATURES) & set(TARGET_FEATURES))


def test_target_features_cover_seven_band_distribution():
    """The 7 spectral bands must all be targetable (they're what the EQ
    drives)."""
    bands = {'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
             'upper_mid_pct', 'presence_pct', 'air_pct'}
    assert bands.issubset(set(TARGET_FEATURES))


def test_distance_features_exclude_spectral_pct_fields():
    """Spectral fractions are targeted, never queried on."""
    spectral = {'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
                'upper_mid_pct', 'presence_pct', 'air_pct',
                'spectral_centroid', 'spectral_rolloff'}
    assert not (set(DISTANCE_FEATURES) & spectral)


# ---------------------------------------------------------------------------
# DistanceStats — z-score fitting
# ---------------------------------------------------------------------------

def test_distance_stats_empty_cloud_returns_neutral_scale():
    """No references → zero means, unit stds; safe to pass to derive_target."""
    stats = DistanceStats.from_references([])
    for f in DISTANCE_FEATURES:
        assert stats.means[f] == 0.0
        assert stats.stds[f] == 1.0


def test_distance_stats_means_match_inputs():
    refs = [
        _fp(tempo_bpm=100.0, crest_db=10.0),
        _fp(tempo_bpm=140.0, crest_db=14.0),
    ]
    stats = DistanceStats.from_references(refs)
    assert stats.means['tempo_bpm'] == pytest.approx(120.0)
    assert stats.means['crest_db'] == pytest.approx(12.0)


def test_distance_stats_constant_feature_clipped_to_epsilon():
    """A feature with zero variance must not produce divide-by-zero downstream."""
    refs = [_fp(tempo_bpm=120.0) for _ in range(5)]
    stats = DistanceStats.from_references(refs)
    assert stats.stds['tempo_bpm'] > 0  # clipped, not zero


# ---------------------------------------------------------------------------
# derive_target — the core operation
# ---------------------------------------------------------------------------

def test_returns_none_for_empty_cloud():
    """Empty cloud → caller falls back."""
    stats = DistanceStats.from_references([])
    assert derive_target(_fp(), references=[], stats=stats) is None


def test_weights_sum_to_one():
    refs = [_fp(track_id=i, tempo_bpm=80.0 + 20 * i) for i in range(5)]
    stats = DistanceStats.from_references(refs)
    result = derive_target(_fp(), refs, stats, k=5)
    assert result is not None
    assert sum(result.weights) == pytest.approx(1.0)


def test_target_interpolates_between_two_clusters():
    """Source equidistant between two clusters → target is the midpoint."""
    bright_refs = [_fp(track_id=i, tempo_bpm=80.0,  air_pct=0.20) for i in range(5)]
    dark_refs   = [_fp(track_id=i, tempo_bpm=160.0, air_pct=0.05) for i in range(5, 10)]
    all_refs    = bright_refs + dark_refs
    stats       = DistanceStats.from_references(all_refs)

    # Source's tempo (120) is equidistant between the two clusters; everything
    # else is identical so distance is dominated by tempo.
    source = _fp(tempo_bpm=120.0)
    result  = derive_target(source, all_refs, stats, k=10)
    assert result is not None
    # Midpoint air_pct is (0.20 + 0.05) / 2 = 0.125
    assert result.target['air_pct'] == pytest.approx(0.125, abs=0.005)


def test_target_skews_toward_nearer_cluster():
    """Source close to bright cluster → target is mostly bright cluster."""
    bright_refs = [_fp(track_id=i, tempo_bpm=80.0,  air_pct=0.20) for i in range(5)]
    dark_refs   = [_fp(track_id=i, tempo_bpm=160.0, air_pct=0.05) for i in range(5, 10)]
    all_refs    = bright_refs + dark_refs
    stats       = DistanceStats.from_references(all_refs)

    # Source's tempo is 85 — very close to the bright cluster (80) and far
    # from dark (160). Target should land closer to bright air_pct (0.20)
    # than to the 0.125 midpoint.
    source = _fp(tempo_bpm=85.0)
    result  = derive_target(source, all_refs, stats, k=10)
    assert result is not None
    assert result.target['air_pct'] > 0.15  # skewed toward bright (0.20)


def test_k_caps_at_cloud_size():
    """If k > len(references), use the whole cloud — no crash, no padding."""
    refs = [_fp(track_id=i) for i in range(3)]
    stats = DistanceStats.from_references(refs)
    result = derive_target(_fp(), refs, stats, k=10)
    assert result is not None
    assert result.n_matched == 3
    assert len(result.weights) == 3
    assert sum(result.weights) == pytest.approx(1.0)


def test_target_falls_back_to_zero_for_missing_features():
    """A reference missing a target field → contributes 0 (not crash)."""
    refs = [{'track_id': 1, **{f: 1.0 for f in DISTANCE_FEATURES}}]  # No target features
    stats = DistanceStats.from_references(refs)
    result = derive_target(_fp(), refs, stats, k=5)
    assert result is not None
    assert result.target['bass_pct'] == 0.0  # default


def test_works_with_orm_like_attribute_access():
    """Module must accept ORM rows (attribute access), not just dicts."""
    class _FpObj:
        __table__ = object()    # signal "I'm an ORM row"
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    base_data = _fp()
    refs = [_FpObj(**base_data) for _ in range(5)]
    stats = DistanceStats.from_references(refs)
    src = _FpObj(**base_data)
    result = derive_target(src, refs, stats, k=5)
    assert result is not None


def test_top_ref_ids_returned_for_debug():
    refs = [_fp(track_id=10 + i, tempo_bpm=80.0 + 20 * i) for i in range(5)]
    stats = DistanceStats.from_references(refs)
    result = derive_target(_fp(tempo_bpm=120.0), refs, stats, k=3)
    assert result is not None
    assert len(result.top_ref_ids) == 3
    assert all(rid in {10, 11, 12, 13, 14} for rid in result.top_ref_ids)


def test_softmax_does_not_overflow_on_large_distances():
    """Distances of 1e6 must not produce NaN/Inf weights."""
    refs = [_fp(track_id=i, tempo_bpm=80.0 + 1e6 * i) for i in range(5)]
    stats = DistanceStats.from_references(refs)
    result = derive_target(_fp(tempo_bpm=0.0), refs, stats, k=5)
    assert result is not None
    assert all(math.isfinite(w) for w in result.weights)


# ---------------------------------------------------------------------------
# #3480 Layer 1 — listening-behavior reference weighting
# ---------------------------------------------------------------------------

def test_reference_weight_zero_falls_back_to_pure_softmax():
    """Every ref at reference_weight=0.0 (unseeded/legacy rows) must behave
    identically to the pre-#3480 unweighted path, not collapse to zero."""
    refs = [_fp(track_id=i, tempo_bpm=80.0 + 20 * i, reference_weight=0.0) for i in range(5)]
    stats = DistanceStats.from_references(refs)

    weighted = derive_target(_fp(), refs, stats, k=5, use_reference_weights=True)
    unweighted = derive_target(_fp(), refs, stats, k=5, use_reference_weights=False)

    assert weighted is not None and unweighted is not None
    assert weighted.weights == pytest.approx(unweighted.weights)
    assert sum(weighted.weights) == pytest.approx(1.0)


def test_reference_weight_pulls_target_toward_heavily_weighted_reference():
    """A reference with a much higher reference_weight should pull the
    target further toward itself than pure distance-based softmax would."""
    # Two references, source equidistant between them (mirrors
    # test_target_interpolates_between_two_clusters), but ref B is far
    # more heavily weighted than ref A.
    ref_a = _fp(track_id=1, tempo_bpm=80.0, air_pct=0.20, reference_weight=0.1)
    ref_b = _fp(track_id=2, tempo_bpm=160.0, air_pct=0.05, reference_weight=5.0)
    refs = [ref_a, ref_b]
    stats = DistanceStats.from_references(refs)
    source = _fp(tempo_bpm=120.0)

    result = derive_target(source, refs, stats, k=2, use_reference_weights=True)
    assert result is not None
    # Pure distance-only midpoint would be 0.125; the heavy weight on ref_b
    # (air_pct=0.05) must pull the target below the unweighted midpoint.
    assert result.target['air_pct'] < 0.125


def test_two_libraries_same_tracks_different_play_counts_produce_different_targets():
    """Acceptance criterion (#3480 Layer 1): two synthetic libraries with the
    same tracks but different listening behavior must derive different EQ
    targets for the same source."""
    def _library(weight_track_2: float) -> list[dict[str, Any]]:
        return [
            _fp(track_id=1, tempo_bpm=80.0,  air_pct=0.20, reference_weight=1.0),
            _fp(track_id=2, tempo_bpm=160.0, air_pct=0.05, reference_weight=weight_track_2),
        ]

    source = _fp(tempo_bpm=120.0)

    library_unplayed = _library(weight_track_2=1.0)   # both refs equally weighted
    library_heavily_played = _library(weight_track_2=10.0)  # track 2 played constantly

    stats_a = DistanceStats.from_references(library_unplayed)
    stats_b = DistanceStats.from_references(library_heavily_played)

    result_a = derive_target(source, library_unplayed, stats_a, k=2)
    result_b = derive_target(source, library_heavily_played, stats_b, k=2)

    assert result_a is not None and result_b is not None
    assert result_a.target['air_pct'] != pytest.approx(result_b.target['air_pct'])
    # The heavily-played-track-2 library must be pulled further toward
    # track 2's air_pct (0.05) than the equally-weighted library.
    assert result_b.target['air_pct'] < result_a.target['air_pct']
