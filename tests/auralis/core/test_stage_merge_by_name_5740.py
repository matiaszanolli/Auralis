"""merge_stage_info reports one entry per stage name (#5740).

The merge compared whole dicts, so a stage whose per-chunk numbers differ
(peak_reduction's target/result) was listed once per chunk although the docs
promise a de-duplicated summary.
"""

from auralis.core.mastering_chunk_assembly import merge_stage_info


def _peak(target, result):
    return {'stage': 'peak_reduction', 'target': target, 'result': result}


def test_a_stage_with_differing_numbers_is_reported_once():
    info = {'stages': []}
    for chunk in ({'stages': [_peak(-0.5, -0.5003)]},
                  {'stages': [_peak(-0.5, -0.4847)]},
                  {'stages': [_peak(-0.5, -0.5018)]}):
        info = merge_stage_info(info, chunk)

    assert info['stages'] == [_peak(-0.5, -0.5003)]


def test_the_first_occurrence_wins():
    info = {'stages': [_peak(-1.0, -1.01)]}

    merged = merge_stage_info(info, {'stages': [_peak(-0.9, -0.95)]})

    assert merged['stages'] == [_peak(-1.0, -1.01)]


def test_a_stage_that_only_engaged_on_a_later_chunk_is_still_reported():
    info = {'stages': [{'stage': 'normalize', 'file_gain': 1.0}]}

    merged = merge_stage_info(info, {'stages': [_peak(-0.5, -0.5), {'stage': 'normalize', 'file_gain': 1.0}]})

    assert [s['stage'] for s in merged['stages']] == ['normalize', 'peak_reduction']


def test_the_first_chunk_info_is_returned_unchanged_when_there_is_no_prior_info():
    chunk = {'stages': [_peak(-0.5, -0.5)]}

    assert merge_stage_info(None, chunk) is chunk
