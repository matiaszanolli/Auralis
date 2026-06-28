"""
Non-WAV truncation detection in load_with_soundfile (#4131).

WAV truncation is caught via the RIFF-declared size. FLAC/AIFF/AU declare a frame
count in their header that sf.read() under-fills when the file is cleanly
truncated, so load_with_soundfile compares len(read) against sf.info().frames.

These tests simulate the truncation by patching the module's soundfile handle so
sf.info() reports the full declared frame count while sf.read() returns fewer.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from auralis.io.loaders import soundfile_loader as mod
from auralis.utils.logging import ModuleError

FULL = 1000
SR = 8000


def _make_flac(tmp_path):
    import soundfile as sf

    p = tmp_path / "a.flac"
    sf.write(str(p), np.zeros((FULL, 2), dtype="float32"), SR)
    return p


def _patch(monkeypatch, read_frames):
    monkeypatch.setattr(
        mod.sf, "info", lambda *a, **k: SimpleNamespace(frames=FULL, duration=FULL / SR)
    )
    monkeypatch.setattr(
        mod.sf,
        "read",
        lambda *a, **k: (np.zeros((read_frames, 2), dtype="float32"), SR),
    )


def test_severely_truncated_nonwav_raises(tmp_path, monkeypatch):
    p = _make_flac(tmp_path)
    _patch(monkeypatch, read_frames=30)  # 3% complete
    with pytest.raises(ModuleError) as ei:
        mod.load_with_soundfile(p)
    assert "truncated" in str(ei.value).lower()


def test_partially_truncated_nonwav_warns(tmp_path, monkeypatch):
    p = _make_flac(tmp_path)
    _patch(monkeypatch, read_frames=500)  # 50% complete
    warned = []
    monkeypatch.setattr(mod, "warning", lambda msg: warned.append(msg))

    audio, sr = mod.load_with_soundfile(p)

    assert sr == SR
    assert len(audio) == 500
    assert any("truncated" in m.lower() for m in warned)


def test_complete_nonwav_no_warning(tmp_path, monkeypatch):
    p = _make_flac(tmp_path)
    _patch(monkeypatch, read_frames=FULL)  # 100% complete
    warned = []
    monkeypatch.setattr(mod, "warning", lambda msg: warned.append(msg))

    audio, sr = mod.load_with_soundfile(p)

    assert len(audio) == FULL
    assert not any("truncated" in m.lower() for m in warned)
