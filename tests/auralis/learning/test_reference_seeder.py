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

    def get_all(self, limit=None, offset=0):
        return list(self._fps)

    def clear_all_reference_flags(self):
        n = sum(1 for fp in self._fps if getattr(fp, 'is_reference', False))
        for fp in self._fps:
            fp.is_reference = False
        self.cleared = n
        return n

    def set_reference_flags(self, track_ids_flagged):
        self.flags_set = dict(track_ids_flagged)
        for fp in self._fps:
            if fp.track_id in track_ids_flagged:
                fp.is_reference = track_ids_flagged[fp.track_id]
        return len(track_ids_flagged)


def _orm_fp(track_id, **overrides):
    base = dict(
        track_id=track_id, lufs=-14.0, crest_db=12.0, is_reference=False,
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


def test_band_fields_match_seven_band_schema():
    """Sanity check: the seeder's band list matches the actual fingerprint fields."""
    expected = {
        'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
        'upper_mid_pct', 'presence_pct', 'air_pct',
    }
    assert set(BAND_FIELDS) == expected
