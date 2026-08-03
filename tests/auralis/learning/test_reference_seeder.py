"""
Tests for the reference cloud seeder.

The seeder scores fingerprints on objective quality heuristics (LUFS, crest,
band balance) and selects the top-N as references. These tests use plain
dicts (not the ORM) to keep the scoring logic verifiable in isolation.
"""

from __future__ import annotations

import pytest

from auralis.learning.reference_seeder import (
    BAND_FIELDS,
    SeederConfig,
    compute_reference_weight,
    refresh_cloud,
    score_fingerprint,
    select_references,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _fp(*, track_id=1, lufs=-14.0, crest_db=12.0, band_overrides=None):
    """Build a fingerprint dict; bands default to a healthy balanced distribution."""
    bands = {
        'sub_bass_pct': 0.05, 'bass_pct': 0.20, 'low_mid_pct': 0.15,
        'mid_pct': 0.25, 'upper_mid_pct': 0.15, 'presence_pct': 0.10,
        'air_pct': 0.10,
    }
    if band_overrides:
        bands.update(band_overrides)
    return {
        'track_id': track_id,
        'lufs': lufs,
        'crest_db': crest_db,
        **bands,
    }


# ---------------------------------------------------------------------------
# Hard requirements
# ---------------------------------------------------------------------------

def test_score_zero_when_lufs_too_loud():
    """LUFS above max (e.g. brick-walled at -7) must score 0."""
    assert score_fingerprint(_fp(lufs=-7.0)) == 0.0


def test_score_zero_when_lufs_too_quiet():
    """LUFS below min (e.g. -25, classical or unmastered) must score 0."""
    assert score_fingerprint(_fp(lufs=-25.0)) == 0.0


def test_score_zero_when_crest_too_low():
    """Very compressed material (crest < 9 dB) must score 0."""
    assert score_fingerprint(_fp(crest_db=6.0)) == 0.0


def test_score_zero_when_one_band_dominates():
    """A track with >65% energy in one band is too unbalanced to reference."""
    assert score_fingerprint(_fp(band_overrides={'bass_pct': 0.70})) == 0.0


def test_score_zero_when_missing_required_field():
    """Missing crest_db → fail hard."""
    bad = _fp()
    del bad['crest_db']
    assert score_fingerprint(bad) == 0.0


# ---------------------------------------------------------------------------
# Soft scoring
# ---------------------------------------------------------------------------

def test_lufs_at_center_scores_highest():
    """LUFS at the center of [min, max] gives the maximum lufs sub-score."""
    config = SeederConfig()
    center = (config.min_lufs + config.max_lufs) / 2  # -14
    center_score = score_fingerprint(_fp(lufs=center))
    edge_score = score_fingerprint(_fp(lufs=config.min_lufs + 0.1))
    assert center_score > edge_score


def test_higher_crest_scores_higher():
    """Within the valid range, more dynamic preservation → higher score."""
    low = score_fingerprint(_fp(crest_db=10.0))
    high = score_fingerprint(_fp(crest_db=17.0))
    assert high > low


def test_balanced_distribution_scores_higher_than_concentrated():
    """Spread-out 7-band distribution beats a more concentrated one."""
    spread = score_fingerprint(_fp(band_overrides={
        'sub_bass_pct': 0.10, 'bass_pct': 0.20, 'low_mid_pct': 0.15,
        'mid_pct': 0.20, 'upper_mid_pct': 0.15, 'presence_pct': 0.10,
        'air_pct': 0.10,
    }))
    concentrated = score_fingerprint(_fp(band_overrides={
        'sub_bass_pct': 0.02, 'bass_pct': 0.55, 'low_mid_pct': 0.10,
        'mid_pct': 0.15, 'upper_mid_pct': 0.10, 'presence_pct': 0.05,
        'air_pct': 0.03,
    }))
    assert spread > concentrated


def test_score_in_zero_one_range():
    """Score must always be in [0, 1]."""
    fp = _fp()
    s = score_fingerprint(fp)
    assert 0.0 <= s <= 1.0


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def test_select_returns_only_positive_scores():
    """Failing candidates are excluded from the result entirely."""
    pool = [
        _fp(track_id=1),                              # good
        _fp(track_id=2, lufs=-25.0),                  # too quiet
        _fp(track_id=3, crest_db=5.0),                # too compressed
        _fp(track_id=4),                              # good
    ]
    # Use generous caps so the test pinpoints filtering, not capping.
    selected = select_references(pool, SeederConfig(max_references_library_fraction=1.0))
    track_ids = [fp['track_id'] for fp, _ in selected]
    assert sorted(track_ids) == [1, 4]


def test_select_caps_at_library_fraction():
    """For a small library (10 tracks), 5% cap = 1 reference (rounded up to 1)."""
    pool = [_fp(track_id=i) for i in range(10)]
    config = SeederConfig(max_references_library_fraction=0.05)
    selected = select_references(pool, config)
    # max(1, int(10 * 0.05)) = max(1, 0) = 1
    assert len(selected) == 1


def test_select_caps_at_absolute_maximum():
    """For a large library, the absolute cap kicks in."""
    pool = [_fp(track_id=i) for i in range(500)]
    config = SeederConfig(max_references_absolute=50, max_references_library_fraction=0.5)
    selected = select_references(pool, config)
    # min(50, int(500 * 0.5)) = min(50, 250) = 50
    assert len(selected) == 50


def test_select_orders_by_score_descending():
    """Best-scoring candidates come first."""
    pool = [
        _fp(track_id=1, lufs=-17.5),    # near edge → lower
        _fp(track_id=2, lufs=-14.0),    # center → higher
        _fp(track_id=3, lufs=-10.5),    # near edge → lower
    ]
    selected = select_references(pool)
    assert selected[0][0]['track_id'] == 2  # center-of-range track wins


def test_select_empty_pool_returns_empty():
    assert select_references([]) == []


# ---------------------------------------------------------------------------
# refresh_cloud orchestration
# ---------------------------------------------------------------------------

class _FakeFingerprint:
    """ORM-row-like object with attribute access."""
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeRepo:
    """In-memory stand-in for FingerprintRepository."""
    def __init__(self, fingerprints):
        self._fps = fingerprints
        self.cleared = 0
        self.flags_set: dict[int, bool] = {}
        self.weights_set: dict[int, float] = {}

    def get_all_with_track_stats(self, limit=None, offset=0):
        return list(self._fps)

    def clear_all_reference_flags(self):
        n = sum(1 for fp in self._fps if getattr(fp, 'is_reference', False))
        for fp in self._fps:
            fp.is_reference = False
            fp.reference_weight = 0.0
        self.cleared = n
        return n

    def set_reference_flags(self, track_ids_flagged):
        self.flags_set = dict(track_ids_flagged)
        for fp in self._fps:
            if fp.track_id in track_ids_flagged:
                fp.is_reference = track_ids_flagged[fp.track_id]
        return len(track_ids_flagged)

    def set_reference_weights(self, weights):
        self.weights_set = dict(weights)
        for fp in self._fps:
            if fp.track_id in weights:
                fp.reference_weight = weights[fp.track_id]
        return len(weights)


def _orm_fp(track_id, **overrides):
    base = dict(
        track_id=track_id, lufs=-14.0, crest_db=12.0, is_reference=False,
        reference_weight=0.0, play_count=0, favorite=False,
        sub_bass_pct=0.05, bass_pct=0.20, low_mid_pct=0.15, mid_pct=0.25,
        upper_mid_pct=0.15, presence_pct=0.10, air_pct=0.10,
    )
    base.update(overrides)
    return _FakeFingerprint(**base)


def test_refresh_cloud_clears_then_reflags():
    pool = [
        _orm_fp(1, is_reference=True),    # previously flagged
        _orm_fp(2, lufs=-14.0),           # good candidate
        _orm_fp(3, lufs=-25.0),           # not a candidate
    ]
    repo = _FakeRepo(pool)
    cleared, selected = refresh_cloud(
        repo, SeederConfig(max_references_library_fraction=1.0),
    )
    assert cleared == 1
    assert selected == 2
    # Tracks 1 and 2 (both good candidates) must be flagged; track 3 must not.
    assert repo.flags_set.get(1) is True
    assert repo.flags_set.get(2) is True
    assert 3 not in repo.flags_set


def test_refresh_cloud_idempotent():
    pool = [_orm_fp(i) for i in range(20)]
    repo = _FakeRepo(pool)
    _, first = refresh_cloud(repo)
    first_flags = dict(repo.flags_set)
    _, second = refresh_cloud(repo)
    second_flags = dict(repo.flags_set)
    assert first == second
    assert first_flags == second_flags


# ---------------------------------------------------------------------------
# #3480 Layer 1 — listening-behavior reference weighting
# ---------------------------------------------------------------------------

def test_compute_reference_weight_unplayed_non_favorite_equals_base_score():
    """No behavioral signal -> weight is exactly the base quality score."""
    fp = _fp(track_id=1)  # play_count/favorite absent -> defaults via _attr_getter
    assert compute_reference_weight(fp, base_score=0.8) == pytest.approx(0.8)


def test_compute_reference_weight_increases_with_play_count():
    quiet = _orm_fp(1, play_count=0, favorite=False)
    played = _orm_fp(2, play_count=200, favorite=False)
    w_quiet = compute_reference_weight(quiet, base_score=0.8)
    w_played = compute_reference_weight(played, base_score=0.8)
    assert w_played > w_quiet


def test_compute_reference_weight_favorite_multiplier():
    plain = _orm_fp(1, play_count=10, favorite=False)
    fav = _orm_fp(2, play_count=10, favorite=True)
    w_plain = compute_reference_weight(plain, base_score=0.8)
    w_fav = compute_reference_weight(fav, base_score=0.8)
    assert w_fav == pytest.approx(w_plain * 1.5)


def test_compute_reference_weight_play_count_has_diminishing_returns():
    """log1p scaling: going from 0->50 plays should matter more than 500->550."""
    w0 = compute_reference_weight(_orm_fp(1, play_count=0), base_score=0.8)
    w50 = compute_reference_weight(_orm_fp(2, play_count=50), base_score=0.8)
    w500 = compute_reference_weight(_orm_fp(3, play_count=500), base_score=0.8)
    w550 = compute_reference_weight(_orm_fp(4, play_count=550), base_score=0.8)
    assert (w50 - w0) > (w550 - w500)


def test_refresh_cloud_writes_reference_weights():
    """Selected references get a nonzero weight; heavily-played ones score higher."""
    pool = [
        _orm_fp(1, play_count=0),      # baseline candidate
        _orm_fp(2, play_count=500),    # heavily played, otherwise identical
        _orm_fp(3, lufs=-25.0),        # disqualified — never selected, never weighted
    ]
    repo = _FakeRepo(pool)
    refresh_cloud(repo, SeederConfig(max_references_library_fraction=1.0))

    assert repo.weights_set[1] > 0.0
    assert repo.weights_set[2] > repo.weights_set[1]
    assert 3 not in repo.weights_set


def test_band_fields_match_seven_band_schema():
    """Sanity check: the seeder's band list matches the actual fingerprint fields."""
    expected = {
        'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
        'upper_mid_pct', 'presence_pct', 'air_pct',
    }
    assert set(BAND_FIELDS) == expected
