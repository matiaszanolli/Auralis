"""Closed-loop quality-gate behavior in the auto-master CLI."""

from pathlib import Path
from unittest.mock import patch

import pytest

import auto_master


def _result(output_path: str, verdict: str) -> dict:
    evaluation = {
        'verdict': verdict,
        'improved_dimensions': (
            ['dynamic_range'] if verdict == 'improved' else []
        ),
        'regressed_dimensions': (
            ['stereo_imaging'] if verdict == 'rejected' else []
        ),
        'artifact_violations': [],
    }
    if verdict == 'unavailable':
        evaluation['reason'] = 'metrics backend failed'
    return {
        'output': output_path,
        'evaluation': evaluation,
    }


class _FakePipeline:
    def __init__(self, verdicts: dict[str, str]):
        self.verdicts = verdicts

    def master_file(self, *, input_path: str, output_path: str, **_kwargs) -> dict:
        Path(output_path).write_bytes(b'candidate')
        verdict = self.verdicts.get(Path(input_path).stem, 'improved')
        return _result(output_path, verdict)


def test_missing_evaluation_fails_closed():
    result = {'output': 'candidate.wav'}

    evaluation = auto_master.get_quality_evaluation(result)

    assert evaluation['verdict'] == 'unavailable'
    assert auto_master.quality_gate_passed(result) is False


@pytest.mark.parametrize(
    ('verdict', 'expected'),
    [
        ('improved', True),
        ('bypass', True),
        ('rejected', False),
        ('unavailable', False),
    ],
)
def test_quality_gate_accepts_only_verified_outcomes(verdict: str, expected: bool):
    assert auto_master.quality_gate_passed(
        _result('candidate.wav', verdict)
    ) is expected


def test_folder_result_aggregates_quality_verdicts(tmp_path: Path):
    input_folder = tmp_path / 'input'
    input_folder.mkdir()
    for name in ('better.wav', 'clean.flac', 'worse.mp3', 'unknown.ogg'):
        (input_folder / name).write_bytes(b'input')

    pipeline = _FakePipeline({
        'better': 'improved',
        'clean': 'bypass',
        'worse': 'rejected',
        'unknown': 'unavailable',
    })
    result = auto_master.master_folder(
        pipeline,
        input_folder,
        tmp_path / 'output',
        intensity=1.0,
        quiet=True,
        time_metrics=False,
    )

    assert result['count'] == 4
    assert result['accepted'] == 2
    assert result['quality'] == {
        'improved': 1,
        'bypass': 1,
        'rejected': 1,
        'unavailable': 1,
    }
    assert {failure['file'] for failure in result['quality_failures']} == {
        'worse.mp3',
        'unknown.ogg',
    }


@pytest.mark.parametrize(
    ('verdict', 'expected_exit'),
    [
        ('improved', 0),
        ('bypass', 0),
        ('rejected', auto_master.QUALITY_GATE_FAILURE_EXIT),
        ('unavailable', auto_master.QUALITY_GATE_FAILURE_EXIT),
    ],
)
def test_single_file_exit_code_reflects_quality_gate(
    tmp_path: Path,
    verdict: str,
    expected_exit: int,
):
    input_path = tmp_path / 'track.wav'
    output_path = tmp_path / 'mastered.wav'
    input_path.write_bytes(b'input')
    pipeline = _FakePipeline({'track': verdict})

    with (
        patch.object(
            auto_master,
            'create_simple_mastering_pipeline',
            return_value=pipeline,
        ),
        patch(
            'sys.argv',
            [
                'auto_master.py',
                str(input_path),
                '--output',
                str(output_path),
                '--quiet',
            ],
        ),
    ):
        exit_code = auto_master.main()

    assert exit_code == expected_exit
    assert output_path.read_bytes() == b'candidate'


def test_folder_exit_code_reports_any_quality_failure(tmp_path: Path):
    input_folder = tmp_path / 'input'
    input_folder.mkdir()
    (input_folder / 'accepted.wav').write_bytes(b'input')
    (input_folder / 'rejected.wav').write_bytes(b'input')
    pipeline = _FakePipeline({
        'accepted': 'improved',
        'rejected': 'rejected',
    })

    with (
        patch.object(
            auto_master,
            'create_simple_mastering_pipeline',
            return_value=pipeline,
        ),
        patch(
            'sys.argv',
            [
                'auto_master.py',
                str(input_folder),
                '--output',
                str(tmp_path / 'output'),
                '--quiet',
            ],
        ),
    ):
        exit_code = auto_master.main()

    assert exit_code == auto_master.QUALITY_GATE_FAILURE_EXIT
