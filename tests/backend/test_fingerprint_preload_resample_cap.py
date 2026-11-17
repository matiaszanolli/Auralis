"""
Regression: pre-loaded fingerprint path crops BEFORE resampling a track too long to analyse whole (#4499)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The pre-loaded-audio branch of _compute_fingerprint() resampled the entire
buffer with librosa.resample(...) and only then cropped to 90s — an O(duration)
resample + full-duration transient allocation on a multi-hour buffer, reopening
the #4116 OOM/latency class. The crop now happens at the source sample rate
first, so resample never sees more than the analysis window of input. A track within
FINGERPRINT_FULL_TRACK_MAX_S is analysed whole (algorithm v13, #6336), so this guard now applies
beyond that limit, and the buffer below is longer than it.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.analysis.fingerprint.fingerprint_service import FingerprintService
from auralis.analysis.fingerprint.windows import FINGERPRINT_BODY_WINDOW_S, FINGERPRINT_FULL_TRACK_MAX_S


def test_resample_receives_at_most_the_body_window(tmp_path):
    svc = FingerprintService(db_path=tmp_path / "fp.db")
    # Don't run the real Rust analyzer — we only care about the resample input.
    svc.analyzer.analyze = lambda *a, **k: {}

    source_sr = 8000  # low, so the buffer stays small; it differs from the analysis rate, forcing a resample
    total_s = int(FINGERPRINT_FULL_TRACK_MAX_S) + 100  # too long to analyse whole
    big = np.zeros((2, source_sr * total_s), dtype=np.float32)

    captured_lengths: list[int] = []

    def spy_resample(y, orig_sr, target_sr):
        captured_lengths.append(int(y.shape[-1]))
        new_len = max(1, int(y.shape[-1] * target_sr / orig_sr))
        return np.zeros(y.shape[:-1] + (new_len,), dtype=np.float32)

    try:
        with patch("librosa.resample", side_effect=spy_resample):
            svc._compute_fingerprint(tmp_path / "x.wav", audio=big, sr=source_sr)
    finally:
        if svc._engine is not None:
            svc._engine.dispose()

    assert captured_lengths, "librosa.resample was never called on the pre-loaded branch"
    cap = int(source_sr * FINGERPRINT_BODY_WINDOW_S)
    assert max(captured_lengths) <= cap, (
        f"resample received {max(captured_lengths)} samples (> {cap} = the body window at source "
        f"rate) — the whole buffer was resampled before cropping (#4499)"
    )
    # And it must be far less than the full buffer.
    assert max(captured_lengths) < source_sr * total_s
