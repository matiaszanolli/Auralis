"""
Whole-file jobs fingerprint a bounded window, like every other 25D producer (#6114)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ContinuousMode fingerprinted whatever it was handed, so a long processing job analysed the whole
decoded file (O(duration) memory and CPU). A buffer longer than FINGERPRINT_FULL_TRACK_MAX_S now
goes through the shared body-window-plus-probes rule; anything shorter is analysed whole, exactly
as before.
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.preloaded_fingerprint import fingerprint_preloaded
from auralis.analysis.fingerprint.windows import (
    FINGERPRINT_BODY_WINDOW_S,
    FINGERPRINT_FULL_TRACK_MAX_S,
    FINGERPRINT_SAMPLE_RATE,
)

SR = 8000  # a low rate keeps the "long" buffer small; the rule is in seconds


class RecordingAnalyzer:
    def __init__(self):
        self.calls: list[tuple[tuple[int, ...], int]] = []

    def analyze(self, audio, sr):
        self.calls.append((audio.shape, sr))
        return {"lufs": -14.0, "crest_db": 12.0}


def _tone(seconds, channels=2):
    t = np.arange(int(SR * seconds), dtype=np.float32) / SR
    mono = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    return np.column_stack([mono] * channels) if channels > 1 else mono


def test_a_track_within_the_whole_track_limit_is_analysed_in_full_and_untouched():
    audio = _tone(30)
    analyzer = RecordingAnalyzer()

    result = fingerprint_preloaded(analyzer, audio, SR)

    assert analyzer.calls == [(audio.shape, SR)]
    assert result == {"lufs": -14.0, "crest_db": 12.0}


def test_a_long_buffer_is_analysed_through_the_body_window_only():
    audio = _tone(FINGERPRINT_FULL_TRACK_MAX_S + 100)
    analyzer = RecordingAnalyzer()

    fingerprint_preloaded(analyzer, audio, SR)

    (shape, rate), = analyzer.calls
    assert rate == FINGERPRINT_SAMPLE_RATE
    body_samples = max(shape)
    assert body_samples <= FINGERPRINT_BODY_WINDOW_S * FINGERPRINT_SAMPLE_RATE
    # bounded by the window, not by the 1000 s of input
    assert body_samples * 4 < audio.shape[0] / SR * FINGERPRINT_SAMPLE_RATE


def test_the_probes_correct_loudness_and_crest_for_a_long_buffer():
    audio = _tone(FINGERPRINT_FULL_TRACK_MAX_S + 100)
    analyzer = RecordingAnalyzer()

    result = fingerprint_preloaded(analyzer, audio, SR)

    # The fake analyzer reports -14 / 12; the median over body + probes of a steady tone replaces them.
    assert result["lufs"] != -14.0
    assert result["crest_db"] == pytest.approx(3.0, abs=0.3)  # a sine's crest is 3 dB


def test_an_analyzer_failure_propagates_instead_of_reading_as_no_fingerprint():
    class Broken:
        def analyze(self, audio, sr):
            raise RuntimeError("engine down")

    with pytest.raises(RuntimeError, match="engine down"):
        fingerprint_preloaded(Broken(), _tone(FINGERPRINT_FULL_TRACK_MAX_S + 10), SR)


def test_a_mono_buffer_works_too():
    analyzer = RecordingAnalyzer()
    fingerprint_preloaded(analyzer, _tone(FINGERPRINT_FULL_TRACK_MAX_S + 10, channels=1), SR)
    assert len(analyzer.calls) == 1


def test_continuous_mode_hands_the_analyzer_a_window_not_the_whole_job():
    """The call site: ContinuousMode._resolve_parameters on a long buffer."""
    from auralis.core.processing.continuous_mode import ContinuousMode

    class EmptyResult(RecordingAnalyzer):
        def analyze(self, audio, sr):
            super().analyze(audio, sr)
            return {}  # "too short to fingerprint": resolution stops right after the analysis

    analyzer = EmptyResult()
    mode = ContinuousMode.__new__(ContinuousMode)
    mode.fingerprint_analyzer = analyzer
    mode.config = type("Config", (), {"internal_sample_rate": SR})()
    mode.last_fingerprint = None

    audio = _tone(FINGERPRINT_FULL_TRACK_MAX_S + 100)

    assert mode._resolve_parameters(audio.copy(), None) is None
    (shape, _), = analyzer.calls
    assert max(shape) < audio.shape[0] / 4  # samples, whichever layout
