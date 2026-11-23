"""ContinuousMode does not pin its working copy across the DSP stages (#6717).

process() used to bind ``processed_audio = target_audio.copy()`` and pass it to
_apply_dsp_stages, so its own frame kept that full-length copy alive through
every stage after the first had replaced it: two more stereo buffers on top of
each stage's peak in a whole-track processing job.
"""

import gc
import weakref

import numpy as np

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.processing.continuous_mode import ContinuousMode


def test_only_the_stages_hold_the_working_copy(monkeypatch):
    released = []
    real = ContinuousMode._apply_dsp_stages

    def spy(self, target_audio, processed_audio, eq_processor, params, *rest, **kwargs):
        assert processed_audio is not target_audio, "the stages must get a copy, not the input"
        probe = weakref.ref(processed_audio)
        working = processed_audio.copy()
        del processed_audio
        gc.collect()
        released.append(probe() is None)
        return real(self, target_audio, working, eq_processor, params, *rest, **kwargs)

    monkeypatch.setattr(ContinuousMode, "_apply_dsp_stages", spy)
    audio = 0.2 * np.random.default_rng(4).standard_normal((44100 * 6, 2))
    original = audio.copy()

    # A copy is made only while the quality comparison reads the original afterwards; by default
    # the stages work in the processor's own validated input (test_whole_track_memory_6717).
    config = UnifiedConfig()
    config.quality_gate_enabled = True
    out = HybridProcessor(config).process(audio)

    assert released == [True], "process() still references the working copy during the stages"
    np.testing.assert_array_equal(audio, original)
    assert out.shape == audio.shape
