"""A probe window that cannot be decoded costs the correction, not the fingerprint (#6326).

The FFmpeg branch decoded both 30 s probes with no guard, so one failure ("Truncated audio file ... got
0.00s") returned None for the whole track, while the librosa branch skipped it silently. Both now skip a
failed or empty probe with a WARNING.
"""

import logging
from pathlib import Path

import numpy as np

from auralis.analysis.fingerprint.probe_decode import decode_probes


def test_a_failing_probe_is_skipped_and_the_others_survive(caplog):
    window = np.ones((2, 100), dtype=np.float32)
    calls: list[float] = []

    def decode(offset_s: float) -> np.ndarray:
        calls.append(offset_s)
        if len(calls) == 1:
            raise RuntimeError("Truncated audio file: got 0.00s")
        return window

    with caplog.at_level(logging.WARNING):
        probes = decode_probes(decode, Path("a.m4a"), total_s=600.0, probe_s=30.0)

    assert len(calls) == 2 and len(probes) == 1
    assert "skipped" in caplog.text and "a.m4a" in caplog.text


def test_an_empty_probe_is_dropped_before_it_reaches_the_median(caplog):
    with caplog.at_level(logging.WARNING):
        probes = decode_probes(lambda off: np.zeros((2, 0), dtype=np.float32), Path("a.m4a"), 600.0, 30.0)

    assert probes == []
    assert "decoded to nothing" in caplog.text


def test_the_ffmpeg_loader_survives_a_failing_probe(monkeypatch, tmp_path):
    from auralis.analysis.fingerprint import windowed_loading as wl

    body = np.ones((2, 22050 * 4), dtype=np.float32)

    def fake_decode(audio_path, tmp, offset_s, dur_s):
        if dur_s == wl.FINGERPRINT_PROBE_WINDOW_S:
            raise RuntimeError("probe failed")
        return body

    monkeypatch.setattr(wl, "_decode_window", fake_decode)
    monkeypatch.setattr("auralis.io.loaders.ffmpeg_probe._probe_audio", lambda p: {"duration": 600.0})

    audio, sr, probes = wl.load_ffmpeg_windows(tmp_path / "a.m4a")

    assert probes == [] and audio.shape[0] == 2 and sr == wl.FINGERPRINT_SAMPLE_RATE
