"""Regression: metadata probes enforce the decode budget (#5312).

``load_audio()`` has always refused a file past ``MAX_DURATION_SECONDS`` /
``oversize_decode_detail()``, but the *probe* paths did not:
``unified_loader.get_audio_info()`` returned whatever duration the container
claimed, and ``chunk_metadata.load_audio_metadata()`` turned that straight into
``total_chunks``. A forged or corrupt header (e.g. a bogus Xing/VBRI frame
count) therefore drove an unbounded per-chunk loop of silence, DSP work and two
log lines per chunk once real EOF was reached.

CONSISTENCY: both sub-functions (``_get_info_with_ffprobe`` and
``_get_info_with_soundfile``) must apply the same rule — capping one container
family only reopens the bug for the other.

SIBLING: the library scanner stores the probed duration at scan time, so the
same cap has to apply there too (``TestScanTimeDurationCap`` below).
"""

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from auralis.io import loader as io_loader
from auralis.io import unified_loader
from auralis.io.loader import oversize_probe_detail
from auralis.io.unified_loader import (
    _get_info_with_ffprobe,
    _get_info_with_soundfile,
    get_audio_info,
)
from auralis.utils.logging import ModuleError


@pytest.fixture
def short_wav(tmp_path: Path) -> Path:
    """A real, perfectly ordinary 2-second WAV."""
    path = tmp_path / "track.wav"
    sf.write(str(path), np.zeros((2 * 44100, 2), dtype=np.float32), 44100)
    return path


def _fake_ffprobe(monkeypatch, *, duration, sample_rate=44100, channels=2):
    """Make unified_loader's ffprobe report exactly this container header."""
    payload = {
        "format": {"duration": duration},
        "streams": [{
            "codec_type": "audio",
            "sample_rate": str(sample_rate),
            "channels": channels,
            "codec_name": "mp3",
            "bit_rate": "320000",
        }],
    }

    class _Result:
        returncode = 0
        stdout = json.dumps(payload)
        stderr = ""

    monkeypatch.setattr(unified_loader, "check_ffprobe", lambda: True)
    monkeypatch.setattr(
        unified_loader.subprocess, "run", lambda *a, **k: _Result()
    )


class TestOversizeProbeDetail:
    """The single rule every probe path shares."""

    def test_unknown_duration_is_not_a_rejection(self):
        # ffmpeg_loader's size-implied fallback (#4128) owns this case.
        assert oversize_probe_detail(None, 44100, 2) is None

    def test_ordinary_track_passes(self):
        assert oversize_probe_detail(212.5, 44100, 2) is None

    def test_duration_over_the_cap_is_reported(self, monkeypatch):
        monkeypatch.setattr(io_loader, "MAX_DURATION_SECONDS", 7200)
        detail = oversize_probe_detail(7201, 44100, 2)
        assert detail and "maximum duration" in detail

    def test_decoded_size_over_budget_is_reported(self, monkeypatch):
        """Duration alone does not bound memory (#4875) — same as the decode paths."""
        monkeypatch.setattr(io_loader, "MAX_DURATION_SECONDS", 7200)
        detail = oversize_probe_detail(7199, 192000, 6)
        assert detail and "decoded size" in detail

    @pytest.mark.parametrize("bogus", [float("inf"), float("nan")])
    def test_non_finite_duration_is_rejected(self, bogus):
        """A forged header can slip NaN/Inf past every `>` comparison."""
        detail = oversize_probe_detail(bogus, 44100, 2)
        assert detail and "non-finite" in detail


class TestSoundfileProbe:
    def test_over_cap_raises_like_load_audio(self, short_wav, monkeypatch):
        monkeypatch.setattr(io_loader, "MAX_DURATION_SECONDS", 1)
        with pytest.raises(ModuleError) as exc:
            _get_info_with_soundfile(short_wav)
        assert "maximum duration" in str(exc.value)

    def test_get_audio_info_reports_the_rejection(self, short_wav, monkeypatch):
        monkeypatch.setattr(io_loader, "MAX_DURATION_SECONDS", 1)
        result = get_audio_info(short_wav)
        assert "maximum duration" in str(result.get("error", ""))
        # No duration for a caller to turn into an unbounded chunk count.
        assert "duration_seconds" not in result

    def test_within_cap_still_probes_normally(self, short_wav):
        result = get_audio_info(short_wav)
        assert "error" not in result
        assert result["duration_seconds"] == pytest.approx(2.0, abs=0.01)


class TestFfprobeProbe:
    def test_forged_duration_raises(self, tmp_path, monkeypatch):
        path = tmp_path / "forged.mp3"
        path.write_bytes(b"\x00" * 512)
        _fake_ffprobe(monkeypatch, duration="360000.0")  # 100 h from a 512-byte file

        with pytest.raises(ModuleError) as exc:
            _get_info_with_ffprobe(path)
        assert "maximum duration" in str(exc.value)

    def test_get_audio_info_reports_the_rejection(self, tmp_path, monkeypatch):
        path = tmp_path / "forged.mp3"
        path.write_bytes(b"\x00" * 512)
        _fake_ffprobe(monkeypatch, duration="360000.0")

        result = get_audio_info(path)
        assert "maximum duration" in str(result.get("error", ""))
        assert "duration_seconds" not in result

    def test_plausible_duration_is_untouched(self, tmp_path, monkeypatch):
        path = tmp_path / "ok.mp3"
        path.write_bytes(b"\x00" * 512)
        _fake_ffprobe(monkeypatch, duration="212.5")

        info = _get_info_with_ffprobe(path)
        assert info["duration_seconds"] == pytest.approx(212.5)
        assert info["sample_rate"] == 44100
        assert info["channels"] == 2


class TestScanTimeDurationCap:
    """SIBLING: catch a forged file at scan time, not only at playback."""

    def _analyzer(self):
        from auralis.library.scanner.audio_analyzer import AudioAnalyzer

        return AudioAnalyzer()

    def test_scan_refuses_a_file_whose_probe_exceeds_the_cap(
        self, short_wav, monkeypatch
    ):
        monkeypatch.setattr(io_loader, "MAX_DURATION_SECONDS", 1)
        assert self._analyzer().extract_audio_info(str(short_wav)) is None

    def test_scan_keeps_an_ordinary_file(self, short_wav):
        info = self._analyzer().extract_audio_info(str(short_wav))
        assert info is not None
        assert info.duration == pytest.approx(2.0, abs=0.01)

    def test_scan_refuses_a_forged_ffprobe_duration(self, tmp_path, monkeypatch):
        """The FFmpeg-only branch (sf.info fails, _probe_audio answers)."""
        from auralis.library.scanner import audio_analyzer as analyzer_mod

        path = tmp_path / "forged.mp3"
        path.write_bytes(b"\x00" * 512)
        monkeypatch.setattr(
            analyzer_mod,
            "_probe_audio",
            lambda p: {"duration": 360000.0, "sample_rate": 44100, "channels": 2},
        )
        assert self._analyzer().extract_audio_info(str(path)) is None
