"""The fingerprint analyses the WHOLE track (v13), not a 90 s window.

Analysis is a property of the entire track; only mastering is chunked. These tests
pin the strategy and its two ways to go wrong: an audible-or-measurable seam where
the track is decoded in segments, and a silent fallback to the old window.
"""

from pathlib import Path

import librosa
import numpy as np
import pytest
import soundfile as sf

from auralis.analysis.fingerprint import track_audio
from auralis.analysis.fingerprint import windows
from auralis.analysis.fingerprint.windowed_compute import compute_windowed_fingerprint
from auralis.analysis.fingerprint.windows import FINGERPRINT_SAMPLE_RATE as FP_SR


def _program(seconds: float, rate: int, channels: int = 2, seed: int = 1) -> np.ndarray:
    """Tones plus noise whose level changes over time, so a mis-joined segment shows."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * rate)) / rate
    base = 0.2 * np.sin(2 * np.pi * 220 * t) + 0.1 * np.sin(2 * np.pi * 3100 * t)
    envelope = 0.6 + 0.4 * np.sin(2 * np.pi * t / 7.0)
    cols = [base * envelope + 0.02 * rng.standard_normal(t.size) for _ in range(channels)]
    return np.stack(cols, axis=1).astype(np.float32)


def _write(path: Path, data: np.ndarray, rate: int) -> Path:
    sf.write(path, data, rate, subtype="FLOAT")
    return path


@pytest.fixture
def small_segments(monkeypatch):
    """10 s segments so a short synthetic file still has several joins."""
    monkeypatch.setattr(track_audio, "FINGERPRINT_SEGMENT_S", 10.0)


class _Capture:
    """Stub analyzer that records exactly what it was asked to analyse."""

    def __init__(self) -> None:
        self.calls: list[tuple[np.ndarray, int]] = []

    def analyze(self, audio, sr):
        self.calls.append((audio.copy(), sr))
        return {f"d{i}": 0.0 for i in range(25)} | {"lufs": -14.0, "crest_db": 12.0}


# ---------------------------------------------------------------------------
# Joining segments must be invisible
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", [44100, 48000, 96000])
def test_segmented_load_equals_a_one_shot_resample(tmp_path, small_segments, rate):
    """Margins are trimmed after resampling, so segments butt together exactly."""
    path = _write(tmp_path / "t.wav", _program(33.0, rate), rate)

    segmented, sr, probes = track_audio.load_track_audio(path)
    one_shot, _ = librosa.load(str(path), sr=FP_SR, mono=False)

    assert sr == FP_SR
    assert probes == []
    assert segmented.shape == one_shot.shape
    # float32 resampler noise is ~1e-7; a seam would be orders of magnitude larger.
    assert np.abs(segmented - one_shot).max() < 1e-5


def test_no_seam_at_the_segment_joins(tmp_path, small_segments):
    path = _write(tmp_path / "t.wav", _program(33.0, 44100), 44100)
    segmented, _, _ = track_audio.load_track_audio(path)
    one_shot, _ = librosa.load(str(path), sr=FP_SR, mono=False)

    for join in (10, 20, 30):
        centre = join * FP_SR
        window = slice(centre - 500, centre + 500)
        assert np.abs(segmented[..., window] - one_shot[..., window]).max() < 1e-5


# ---------------------------------------------------------------------------
# Whole track vs the windowed fallback
# ---------------------------------------------------------------------------


def test_a_short_track_is_analysed_whole_with_no_probes(tmp_path):
    path = _write(tmp_path / "t.wav", _program(40.0, 44100), 44100)
    stub = _Capture()

    compute_windowed_fingerprint(stub, path)

    audio, sr = stub.calls[0]
    assert len(stub.calls) == 1
    assert sr == FP_SR
    assert audio.shape[-1] == pytest.approx(40.0 * FP_SR, abs=FP_SR)


def test_analyzer_values_stand_when_the_whole_track_is_analysed(tmp_path):
    """The probe median (#4595) only existed to repair a single window's bias."""
    path = _write(tmp_path / "t.wav", _program(40.0, 44100), 44100)

    fingerprint = compute_windowed_fingerprint(_Capture(), path)

    assert fingerprint is not None
    assert fingerprint["lufs"] == -14.0
    assert fingerprint["crest_db"] == 12.0


def test_the_whole_track_is_not_copied_to_float64(tmp_path):
    path = _write(tmp_path / "t.wav", _program(20.0, 44100), 44100)
    stub = _Capture()

    compute_windowed_fingerprint(stub, path)

    assert stub.calls[0][0].dtype == np.float32


def test_a_track_over_the_cap_falls_back_to_body_and_probe_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(windows, "FINGERPRINT_FULL_TRACK_MAX_S", 10.0)
    path = _write(tmp_path / "long.wav", _program(40.0, 44100), 44100)

    audio, _sr, probes = track_audio.load_track_audio(path)

    assert len(probes) == 2
    assert audio.shape[-1] == 40 * FP_SR  # 40 s < the 90 s body window: whole file, once


def test_the_cap_is_inclusive():
    assert windows.analyses_whole_track(windows.FINGERPRINT_FULL_TRACK_MAX_S)
    assert not windows.analyses_whole_track(windows.FINGERPRINT_FULL_TRACK_MAX_S + 0.1)
    assert not windows.analyses_whole_track(None)
    assert not windows.analyses_whole_track(0.0)


# ---------------------------------------------------------------------------
# Channel layouts
# ---------------------------------------------------------------------------


def test_a_mono_file_is_analysed_whole(tmp_path, small_segments):
    path = _write(tmp_path / "mono.wav", _program(25.0, 44100, channels=1)[:, 0], 44100)

    audio, _, probes = track_audio.load_track_audio(path)

    assert probes == []
    assert audio.shape == (25 * FP_SR,)


def test_surround_is_folded_per_segment_and_the_lfe_is_dropped(tmp_path, small_segments):
    rate = 44100
    frames = int(25.0 * rate)
    lfe_only = np.zeros((frames, 6), dtype=np.float32)
    lfe_only[:, 3] = 0.5 * np.sin(2 * np.pi * 50 * np.arange(frames) / rate)
    centre_only = np.zeros((frames, 6), dtype=np.float32)
    centre_only[:, 2] = 0.5 * np.sin(2 * np.pi * 440 * np.arange(frames) / rate)

    lfe, _, _ = track_audio.load_track_audio(_write(tmp_path / "lfe.wav", lfe_only, rate))
    centre, _, _ = track_audio.load_track_audio(_write(tmp_path / "centre.wav", centre_only, rate))

    assert lfe.shape[0] == 2 and np.sqrt(np.mean(lfe**2)) < 1e-6
    assert centre.shape[0] == 2 and np.sqrt(np.mean(centre**2)) > 0.05


def test_a_preloaded_buffer_is_analysed_whole():
    rate = 44100
    raw = _program(30.0, rate).T  # (channels, samples)

    audio, sr, probes = track_audio.load_track_audio(Path('preloaded.wav'), raw, rate)

    assert probes == []
    assert sr == FP_SR
    assert audio.shape == (2, 30 * FP_SR)


# ---------------------------------------------------------------------------
# Old fingerprints must be recomputed
# ---------------------------------------------------------------------------


def test_the_algorithm_version_invalidates_windowed_fingerprints():
    from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION

    assert FINGERPRINT_ALGORITHM_VERSION >= 13


# ---------------------------------------------------------------------------
# Memory budget: whole-track analysis must not scale with the worker count
# ---------------------------------------------------------------------------


class TestAnalysisBudget:
    def test_an_oversized_job_is_admitted_when_nothing_else_runs(self):
        from auralis.analysis.fingerprint.analysis_budget import AnalysisBudget

        budget = AnalysisBudget(capacity_minutes=10.0)

        with budget.reserve(500.0):  # far over capacity: must not deadlock
            pass

    def test_a_second_job_waits_for_room_then_runs(self):
        import threading

        from auralis.analysis.fingerprint.analysis_budget import AnalysisBudget

        budget = AnalysisBudget(capacity_minutes=10.0)
        order: list[str] = []
        first_in = threading.Event()
        release_first = threading.Event()

        def first():
            with budget.reserve(8.0):
                order.append("first-in")
                first_in.set()
                release_first.wait(5)
                order.append("first-out")

        def second():
            first_in.wait(5)
            with budget.reserve(8.0):  # 8 + 8 > 10: must wait
                order.append("second-in")

        threads = [threading.Thread(target=first), threading.Thread(target=second)]
        for th in threads:
            th.start()
        first_in.wait(5)
        threads[1].join(0.3)
        assert threads[1].is_alive(), "second job ran while the budget was full"
        release_first.set()
        for th in threads:
            th.join(5)

        assert order == ["first-in", "first-out", "second-in"]

    def test_small_jobs_run_together(self):
        from auralis.analysis.fingerprint.analysis_budget import AnalysisBudget

        budget = AnalysisBudget(capacity_minutes=40.0)

        with budget.reserve(4.0), budget.reserve(4.0), budget.reserve(4.0):
            assert budget._in_flight == pytest.approx(12.0)

        assert budget._in_flight == 0.0

    def test_the_reservation_is_released_when_analysis_raises(self):
        from auralis.analysis.fingerprint.analysis_budget import AnalysisBudget

        budget = AnalysisBudget(capacity_minutes=10.0)

        with pytest.raises(RuntimeError):
            with budget.reserve(9.0):
                raise RuntimeError("analyzer failed")

        assert budget._in_flight == 0.0
