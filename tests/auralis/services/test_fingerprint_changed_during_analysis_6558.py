"""A file replaced while it is analysed gets no fingerprint row and no sidecar (#6558).

extract_and_store decoded and analysed the file, then upserted with a guard that
only checked the path, and SidecarManager.write stat()ed the audio AFTER the
fact. A file replaced mid-analysis had the OLD audio's fingerprint stored as
current and its sidecar stamped with the NEW file's size/mtime, so is_valid()
accepted it indefinitely. The file is now stat()ed before the analysis and
re-checked before storing; the sidecar records that pre-analysis stat, and the
worker releases the claim instead of counting a failure.
"""

import os
from unittest.mock import MagicMock

import pytest

from auralis.analysis.fingerprint.metrics.constants import FINGERPRINT_DIMENSION_NAMES
from auralis.services.fingerprint_extractor import AudioChangedDuringAnalysis, FingerprintExtractor
from auralis.services.fingerprint_worker import FingerprintWorkerExecution

FINGERPRINT = {name: 0.5 for name in FINGERPRINT_DIMENSION_NAMES}


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "song.flac"
    path.write_bytes(b"x" * 1000)
    os.utime(path, (1_700_000_000, 1_700_000_000))
    return path


def _extractor(monkeypatch, replace_during_analysis: bool):
    repo = MagicMock()
    repo.upsert.return_value = True
    extractor = FingerprintExtractor(repo, use_sidecar_files=True)
    extractor.sidecar_manager = MagicMock()
    extractor.sidecar_manager.is_valid.return_value = False

    def analyse(track_id, path, should_stop=None):
        if replace_during_analysis:
            path.write_bytes(b"y" * 2000)  # a re-rip lands mid-analysis
        return dict(FINGERPRINT)

    monkeypatch.setattr(extractor, "_compute_fingerprint", analyse)
    return extractor, repo


def test_a_file_replaced_mid_analysis_is_neither_stored_nor_sidecarred(audio, monkeypatch):
    extractor, repo = _extractor(monkeypatch, replace_during_analysis=True)

    with pytest.raises(AudioChangedDuringAnalysis):
        extractor.extract_and_store(7, str(audio))

    repo.upsert.assert_not_called()
    extractor.sidecar_manager.write.assert_not_called()


def test_the_sidecar_records_the_pre_analysis_stat(audio, monkeypatch):
    extractor, repo = _extractor(monkeypatch, replace_during_analysis=False)
    before = audio.stat()

    assert extractor.extract_and_store(7, str(audio)) is True

    repo.upsert.assert_called_once()
    stamped = extractor.sidecar_manager.write.call_args.kwargs["audio_stat"]
    assert (stamped.st_size, stamped.st_mtime) == (before.st_size, before.st_mtime)


def test_the_worker_releases_the_claim_without_counting_a_failure(monkeypatch):
    worker = FingerprintWorkerExecution.__new__(FingerprintWorkerExecution)
    worker.processing_semaphore = MagicMock(usage=(0, 8))
    worker.stats = {"processing": 0, "completed": 0, "failed": 0, "total_time": 0.0}
    worker.stats_lock = MagicMock()
    worker.stats_lock.__enter__ = lambda s: None
    worker.stats_lock.__exit__ = lambda s, *a: None
    worker.should_stop = False
    scheduler = MagicMock()
    worker._get_repository_factory = lambda: MagicMock(fingerprint_scheduler=scheduler)
    worker._release_failed_claim = MagicMock()
    worker._report_progress = MagicMock()

    def changed(*_args, **_kwargs):
        raise AudioChangedDuringAnalysis("song.flac changed while it was analysed")

    monkeypatch.setattr(worker, "_extract_bounded", changed)
    worker._process_track(MagicMock(id=7, filepath="/m/song.flac"), worker_id=0)

    scheduler.release_claim.assert_called_once_with(7)
    worker._release_failed_claim.assert_not_called()
    assert worker.stats["failed"] == 0
