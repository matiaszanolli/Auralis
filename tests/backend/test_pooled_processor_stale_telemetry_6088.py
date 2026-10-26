"""
Regression tests: a pooled processor must not report the previous job's profile (#6088).

``validate_and_normalize_input`` returns for an empty, <1024-sample or all-zero
input before any analysis runs, so ``last_content_profile`` and
``continuous_mode.last_fingerprint`` still described the previous job and
``finalize_job`` wrote that job's LUFS into the silent file's result.
"""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from core.job_execution import _reset_processor_state
from core.job_finalize import finalize_job
from core.job_models import ProcessingJob

SAMPLE_RATE = 44100
PREVIOUS_JOB_LUFS = -9.0


@pytest.fixture
def processor():
    proc = HybridProcessor(UnifiedConfig())
    yield proc
    proc.close()


def _pretend_previous_job_ran(proc: HybridProcessor) -> None:
    fingerprint = {"lufs": PREVIOUS_JOB_LUFS}
    proc.continuous_mode.last_fingerprint = fingerprint
    proc.continuous_mode.last_coordinates = object()
    proc.continuous_mode.last_parameters = object()
    proc.last_content_profile = {"fingerprint": fingerprint, "estimated_lufs": PREVIOUS_JOB_LUFS}
    proc.adaptive_mode.last_content_profile = {"bass_energy_pct": 40.0}


def _finalized_lufs(proc: HybridProcessor, audio: np.ndarray, tmp_path: Path) -> float | None:
    job = ProcessingJob("job", "/in.wav", str(tmp_path / "out.wav"), {}, mode="adaptive")
    job.started_at = datetime.now()
    finalize_job(job, audio, SAMPLE_RATE, proc)
    return job.result_data["lufs"]


@pytest.mark.parametrize(
    "degenerate",
    [
        pytest.param(np.zeros((3 * SAMPLE_RATE, 2)), id="3s-silence"),
        pytest.param(np.full((100, 2), 0.2), id="shorter-than-min-samples"),
        pytest.param(np.zeros((0, 2)), id="empty"),
    ],
)
def test_degenerate_job_after_a_normal_one_reports_no_stale_lufs(processor, degenerate, tmp_path):
    _pretend_previous_job_ran(processor)
    # Sanity: without the job-boundary reset the stale value would be reported.
    assert _finalized_lufs(processor, degenerate, tmp_path) == PREVIOUS_JOB_LUFS

    _pretend_previous_job_ran(processor)
    _reset_processor_state(processor)
    processor.process(degenerate)

    assert _finalized_lufs(processor, degenerate, tmp_path) is None


def test_reset_run_state_clears_every_last_field(processor):
    _pretend_previous_job_ran(processor)

    processor.reset_run_state()

    assert processor.last_content_profile == {}
    assert processor.adaptive_mode.last_content_profile is None
    assert processor.continuous_mode.last_fingerprint is None
    assert processor.continuous_mode.last_coordinates is None
    assert processor.continuous_mode.last_parameters is None


def test_a_later_normal_job_still_reports_its_own_lufs(processor, tmp_path):
    _pretend_previous_job_ran(processor)
    _reset_processor_state(processor)

    processor.continuous_mode.last_fingerprint = {"lufs": -14.5}

    assert _finalized_lufs(processor, np.zeros((SAMPLE_RATE, 2)), tmp_path) == -14.5
