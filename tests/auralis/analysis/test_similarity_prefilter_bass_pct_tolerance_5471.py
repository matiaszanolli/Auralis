"""
Similarity pre-filter's bass_pct tolerance must be fraction-scale, not
percent-scale (#5471).

bass_pct is a Unit.FRACTION dimension bounded to (0.05, 0.50) -- see
auralis/analysis/fingerprint/schema.py. `_get_prefiltered_candidates` used
to build its range with a `+/- 8.0` tolerance, ~16-160x the field's entire
valid span, so the computed (lower, upper) bound always contained every
possible value: a permanent no-op for that dimension in the pre-filter.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from unittest.mock import Mock

from auralis.analysis.fingerprint.similarity import FingerprintSimilarity


def _target_fp(bass_pct: float = 0.20) -> Mock:
    fp = Mock()
    fp.track_id = 1
    fp.lufs = -12.0
    fp.crest_db = 8.0
    fp.bass_pct = bass_pct
    fp.tempo_bpm = 120.0
    return fp


def test_bass_pct_range_uses_fraction_scale_tolerance():
    repo = Mock()
    repo.get_by_multi_dimension_range = Mock(return_value=[])

    similarity = FingerprintSimilarity(repo)
    similarity._get_prefiltered_candidates(_target_fp(bass_pct=0.20))

    ranges = repo.get_by_multi_dimension_range.call_args.args[0]
    lower, upper = ranges['bass_pct']

    # +/- 0.08 around 0.20, not +/- 8.0.
    assert lower == 0.20 - 0.08
    assert upper == 0.20 + 0.08


def test_bass_pct_range_no_longer_spans_the_entire_valid_domain():
    """The whole valid range is (0.05, 0.50) -- a correctly-scaled +/- 0.08
    tolerance must exclude at least some of it, unlike the old +/- 8.0."""
    repo = Mock()
    repo.get_by_multi_dimension_range = Mock(return_value=[])

    similarity = FingerprintSimilarity(repo)
    similarity._get_prefiltered_candidates(_target_fp(bass_pct=0.20))

    ranges = repo.get_by_multi_dimension_range.call_args.args[0]
    lower, upper = ranges['bass_pct']

    FIELD_MIN, FIELD_MAX = 0.05, 0.50
    assert not (lower <= FIELD_MIN and upper >= FIELD_MAX), (
        "bass_pct range still spans the field's entire valid domain -- "
        "the pre-filter dimension is still a no-op"
    )


def test_other_dimension_tolerances_unchanged():
    """Only bass_pct was mis-scaled; lufs/crest_db/tempo_bpm keep their tolerances."""
    repo = Mock()
    repo.get_by_multi_dimension_range = Mock(return_value=[])

    similarity = FingerprintSimilarity(repo)
    fp = _target_fp()
    similarity._get_prefiltered_candidates(fp)

    ranges = repo.get_by_multi_dimension_range.call_args.args[0]
    assert ranges['lufs'] == (fp.lufs - 3.0, fp.lufs + 3.0)
    assert ranges['crest_db'] == (fp.crest_db - 2.0, fp.crest_db + 2.0)
    assert ranges['tempo_bpm'] == (fp.tempo_bpm - 15.0, fp.tempo_bpm + 15.0)
