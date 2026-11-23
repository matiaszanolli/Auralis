"""Regression tests: one process() K-weights each distinct buffer once
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A whole-track ``HybridProcessor.process()`` called ``calculate_loudness_units``
11 times on 6 distinct signals: the input three times (the #5700 K-offset, the
input snapshot, the EQ guard's "before"), the EQ output twice (snapshot and the
guard's "after"), the normalised output three times (two debug lines and the
snapshot), and on real music, where the phase guard rarely fires, the stereo
stage's output twice. One reading of a whole track costs as much as a DSP stage.
The readings are now shared through ``PipelineJournal.lufs()`` and passed down
from ``ContinuousMode.process()``.
"""

import gc
import hashlib
import sys

import numpy as np
import pytest

import auralis.dsp.utils.adaptive as adaptive
from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.processing.stage_snapshot import PipelineJournal

SR = 44100


def _uncorrelated_noise(seconds: float = 15.0) -> np.ndarray:
    return np.random.default_rng(1).standard_normal((int(SR * seconds), 2)) * 0.1


def _correlated_noise(seconds: float = 15.0) -> np.ndarray:
    """Mostly-shared L/R content: the phase guard leaves it alone, like real music."""
    rng = np.random.default_rng(2)
    common = rng.standard_normal(int(SR * seconds))
    left = common + 0.2 * rng.standard_normal(len(common))
    right = common + 0.2 * rng.standard_normal(len(common))
    return np.stack([left, right], axis=1) * 0.08


def _record_measurements(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Patch every module-level binding of calculate_loudness_units; return the content hashes it sees."""
    original = adaptive.calculate_loudness_units
    seen: list[str] = []

    def recording(audio: np.ndarray, sample_rate: int) -> float:
        seen.append(hashlib.sha1(np.ascontiguousarray(audio).tobytes()).hexdigest())
        return original(audio, sample_rate)

    for name, module in list(sys.modules.items()):
        if name.startswith("auralis") and getattr(module, "calculate_loudness_units", None) is original:
            monkeypatch.setattr(module, "calculate_loudness_units", recording)
    return seen


@pytest.mark.parametrize("make_audio", [_uncorrelated_noise, _correlated_noise], ids=["uncorrelated", "correlated"])
def test_process_measures_each_distinct_buffer_once(monkeypatch, make_audio):
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)
    audio = make_audio()
    processor.process(audio[: SR * 5])  # first-call setup is not what this test is about

    seen = _record_measurements(monkeypatch)
    processor.process(audio)

    # Input, after EQ, after dynamics, after stereo, after normalisation at least.
    assert len(seen) >= 5
    repeated = len(seen) - len(set(seen))
    assert repeated == 0, f"{repeated} of {len(seen)} loudness measurements re-measured an already-measured buffer"


def test_journal_lufs_reuses_the_latest_snapshot_of_the_same_buffer(monkeypatch):
    journal = PipelineJournal(SR)
    audio = _uncorrelated_noise(2.0)
    snap = journal.snapshot(audio, "input")
    seen = _record_measurements(monkeypatch)

    assert journal.lufs(audio) == snap.lufs
    assert seen == []


def test_journal_lufs_measures_a_different_buffer_even_with_equal_content(monkeypatch):
    journal = PipelineJournal(SR)
    audio = _uncorrelated_noise(2.0)
    journal.snapshot(audio, "input")
    louder = audio * 2.0
    seen = _record_measurements(monkeypatch)

    assert journal.lufs(louder) == pytest.approx(adaptive.calculate_loudness_units(louder, SR))
    # A copy is a different buffer: matched by identity, never assumed equal.
    journal.lufs(audio.copy())
    assert len(seen) == 3  # louder (twice: once by the journal, once by the assertion) and the copy


def test_journal_does_not_keep_the_snapshot_buffer_alive():
    journal = PipelineJournal(SR)
    audio = _uncorrelated_noise(2.0)
    journal.snapshot(audio, "input")
    latest = journal._latest_lufs  # noqa: SLF001 - the weak reference is the point of the test
    assert latest is not None
    ref = latest[0]
    del audio
    gc.collect()
    assert ref() is None
