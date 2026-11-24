"""Tier-3 extraction lets an engine failure through and keeps a track failure soft (#6492).

``extract_from_audio`` and ``compute_windowed_fingerprint`` caught every exception and returned
None, so a broken engine (``FingerprintUnavailable``) at the whole-track step silently left the
stream mastering each chunk on its own, against #6107. It now propagates from the stream's tier-3
extraction and fails the stream through the mapped error; any other failure still returns None,
and the stream reports the fingerprint status "failed" (see the #6507 status tests).
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.analysis.fingerprint import windowed_compute  # noqa: E402
from auralis.analysis.fingerprint.analysis_budget import AnalysisCancelled  # noqa: E402
from auralis.analysis.fingerprint.audio_fingerprint_analyzer import FingerprintUnavailable  # noqa: E402
from core import fingerprint_loading  # noqa: E402
from core.job_error_mapping import _safe_error_message  # noqa: E402
from core.mastering_target_service import MasteringTargetService  # noqa: E402

SR = 44100


class _BrokenEngine:
    def analyze(self, audio, sr):
        raise FingerprintUnavailable("Rust module missing")


def _audio() -> np.ndarray:
    return np.zeros((2, SR * 20), dtype=np.float32)


def test_the_stream_path_lets_an_engine_failure_through():
    with pytest.raises(FingerprintUnavailable):
        windowed_compute.compute_windowed_fingerprint(
            _BrokenEngine(), Path("t.wav"), _audio(), SR, raise_unavailable=True
        )


def test_the_background_path_still_reads_an_engine_failure_as_no_fingerprint():
    assert windowed_compute.compute_windowed_fingerprint(_BrokenEngine(), Path("t.wav"), _audio(), SR) is None


def test_a_cancelled_wait_still_returns_none_on_the_stream_path():
    with patch.object(windowed_compute.analysis_budget, "reserve", side_effect=AnalysisCancelled()):
        result = windowed_compute.compute_windowed_fingerprint(
            _BrokenEngine(), Path("t.wav"), _audio(), SR, raise_unavailable=True
        )
    assert result is None


def test_extract_from_audio_reraises_an_engine_failure_and_softens_the_rest(tmp_path):
    track = tmp_path / "t.flac"
    track.write_bytes(b"not audio")
    derive = lambda fp: {}  # noqa: E731

    with patch.object(windowed_compute, "compute_windowed_fingerprint", side_effect=FingerprintUnavailable("x")):
        with pytest.raises(FingerprintUnavailable):
            fingerprint_loading.extract_from_audio(str(track), derive, save_to_file=False)
    with patch.object(windowed_compute, "compute_windowed_fingerprint", return_value=None):
        assert fingerprint_loading.extract_from_audio(str(track), derive, save_to_file=False) is None


def test_the_engine_failure_reaches_the_stream_as_its_mapped_error_and_frees_the_flight(tmp_path):
    track = tmp_path / "t.flac"
    track.write_bytes(b"not audio")
    service = MasteringTargetService(get_fingerprints_repository=lambda: None)

    with patch.object(windowed_compute, "compute_windowed_fingerprint", side_effect=FingerprintUnavailable("x")):
        for _ in range(2):  # the second call is not stuck behind the first one's single-flight claim
            with pytest.raises(FingerprintUnavailable) as raised:
                service.load_fingerprint(7, str(track), save_extracted=False, file_signature="sig")

    assert _safe_error_message(raised.value) == "Audio analysis failed; the track was not mastered"
