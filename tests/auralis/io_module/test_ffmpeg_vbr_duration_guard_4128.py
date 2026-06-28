"""
Pre-decode duration guard for files ffprobe can't measure (#4128).

A true-VBR MP3 without a Xing/VBRI header makes ffprobe omit the duration, so
expected_duration stayed None and the pre-decode guard was bypassed — FFmpeg
decoded the whole file to a temp WAV before the post-decode check fired. The
loader now falls back to a file-size-based lower-bound estimate.
"""

import pytest

import auralis.io.loader as loadermod
from auralis.io.loaders import ffmpeg_loader as mod
from auralis.utils.logging import ModuleError


def _stub_environment(monkeypatch):
    monkeypatch.setattr(mod, "check_ffmpeg", lambda: True)
    monkeypatch.setattr(mod, "check_ffprobe", lambda: True)
    monkeypatch.setattr(
        mod,
        "_probe_audio",
        lambda p: {"duration": None, "sample_rate": 44100, "channels": 2},
    )


def test_no_duration_oversized_rejected_before_decode(tmp_path, monkeypatch):
    f = tmp_path / "vbr.mp3"
    f.write_bytes(b"\x00" * 10_000)  # 10 KB -> ~0.04s at the 2 Mbps ceiling
    _stub_environment(monkeypatch)
    # Tiny ceiling so the 10 KB file's size-implied duration exceeds it.
    monkeypatch.setattr(loadermod, "MAX_DURATION_SECONDS", 0.01)

    # subprocess must never run — rejection happens before any decode.
    def fail_if_called(*a, **k):
        raise AssertionError("FFmpeg decode should not run for an oversized file")

    monkeypatch.setattr(mod.subprocess, "run", fail_if_called)

    with pytest.raises(ModuleError) as ei:
        mod.load_with_ffmpeg(f)
    assert "maximum duration" in str(ei.value)


def test_no_duration_within_limits_passes_guard(tmp_path, monkeypatch):
    f = tmp_path / "vbr_ok.mp3"
    f.write_bytes(b"\x00" * 10_000)
    _stub_environment(monkeypatch)
    monkeypatch.setattr(loadermod, "MAX_DURATION_SECONDS", 7200)

    # Prove we got past the duration guard into the conversion step.
    def reached_conversion(*a, **k):
        raise RuntimeError("REACHED_CONVERSION")

    monkeypatch.setattr(mod.subprocess, "run", reached_conversion)

    with pytest.raises(Exception) as ei:
        mod.load_with_ffmpeg(f)
    assert "maximum duration" not in str(ei.value)
