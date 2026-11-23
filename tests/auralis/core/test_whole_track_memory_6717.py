"""A whole-track process() holds a bounded number of track-sized buffers (#6717).

Processing jobs decode a whole file and call HybridProcessor.process() once,
so its peak memory is a multiple of the track. It was ~28x the input; each
stage now keeps at most its output plus one working buffer, and the validated
input (which HybridProcessor creates itself) is the stages' working buffer
rather than a copy of it whenever nothing reads the original afterwards.
"""

import tracemalloc

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.processing.continuous_mode import ContinuousMode

SR = 44_100


def _traced_peak_ratio(audio: np.ndarray) -> float:
    processor = HybridProcessor(UnifiedConfig())
    processor.process(audio[: SR * 5])  # first-call setup outside the measurement
    tracemalloc.start()
    try:
        start = tracemalloc.get_traced_memory()[0]
        out = processor.process(audio)
        peak = tracemalloc.get_traced_memory()[1] - start
    finally:
        tracemalloc.stop()
    assert out is not None and out.shape == (len(audio), 2)
    return peak / audio.nbytes


def test_mono_whole_track_peak_stays_under_seven_times_the_input():
    # Mono is the worst case: the pipeline works in stereo, twice the input's size.
    # Measured ~6.0x; it was 8.0x while the stages worked on a copy of the input.
    audio = 0.1 * np.random.default_rng(1).standard_normal(SR * 30)
    ratio = _traced_peak_ratio(audio)
    assert ratio <= 7.0, f"process() peaked at {ratio:.2f}x a mono input"


def _stage_input(monkeypatch, quality_gate_enabled: bool) -> tuple[bool, np.ndarray, np.ndarray]:
    """Run process() and report whether the stages were handed the validated input itself."""
    seen: dict[str, bool] = {}
    real = ContinuousMode._apply_dsp_stages

    def spy(self, target_audio, processed_audio, *rest, **kwargs):
        seen["same"] = processed_audio is target_audio
        return real(self, target_audio, processed_audio, *rest, **kwargs)

    monkeypatch.setattr(ContinuousMode, "_apply_dsp_stages", spy)
    config = UnifiedConfig()
    config.quality_gate_enabled = quality_gate_enabled
    audio = 0.2 * np.random.default_rng(2).standard_normal((SR * 6, 2))
    original = audio.copy()
    HybridProcessor(config).process(audio)
    return seen["same"], audio, original


def test_the_stages_work_in_the_validated_input_when_nothing_reads_it_later(monkeypatch):
    same, audio, original = _stage_input(monkeypatch, quality_gate_enabled=False)
    assert same
    np.testing.assert_array_equal(audio, original)  # the caller's own array is never touched


def test_the_quality_comparison_keeps_its_untouched_original(monkeypatch):
    same, audio, original = _stage_input(monkeypatch, quality_gate_enabled=True)
    assert not same
    np.testing.assert_array_equal(audio, original)


@pytest.mark.parametrize("quality_gate_enabled", [False, True])
def test_output_does_not_depend_on_which_buffer_the_stages_used(quality_gate_enabled):
    audio = 0.2 * np.random.default_rng(3).standard_normal((SR * 6, 2))
    config = UnifiedConfig()
    config.quality_gate_enabled = quality_gate_enabled
    reference = UnifiedConfig()
    reference.quality_gate_enabled = not quality_gate_enabled

    np.testing.assert_array_equal(HybridProcessor(config).process(audio), HybridProcessor(reference).process(audio))
