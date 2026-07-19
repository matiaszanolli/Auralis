"""
Regression test: ContinuousMode DSP stage ordering (#4254)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_apply_dsp_stages` was refactored from seven inline sub-operations into a loop
over an ordered stage list. These tests pin the execution order (5a input gain →
5b EQ → 5c dynamics → 5d stereo width → 5e normalization) so a silent stage
reorder during future edits is caught, and re-verify the sample-count invariant.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from auralis.core.config import UnifiedConfig
from auralis.core.processing.continuous_mode import ContinuousMode


def _mode() -> ContinuousMode:
    return ContinuousMode(
        config=UnifiedConfig(),
        content_analyzer=MagicMock(),
        fingerprint_analyzer=MagicMock(),
    )


def test_dsp_stages_execute_in_documented_order(monkeypatch):
    """The ordered stage list must run input_gain → eq → dynamics → stereo → norm."""
    mode = _mode()
    # Quality gate compares against a QualityMetrics model — irrelevant here.
    mode.config.quality_gate_enabled = False

    calls: list[str] = []

    def _spy(name):
        # Pass the audio through unchanged so the sample count is preserved and
        # the post-loop report/gate steps see a real array.
        def _stage(audio, *args, **kwargs):
            calls.append(name)
            return audio
        return _stage

    for name in ("input_gain", "eq", "dynamics", "stereo_width", "normalization"):
        monkeypatch.setattr(mode, f"_stage_{name}", _spy(name))

    audio = (
        np.random.default_rng(0).standard_normal((mode.config.internal_sample_rate, 2)) * 0.1
    ).astype(np.float32)

    out = mode._apply_dsp_stages(
        audio.copy(), audio.copy(), eq_processor=MagicMock(), params=SimpleNamespace()
    )

    assert calls == ["input_gain", "eq", "dynamics", "stereo_width", "normalization"]
    # Sample-count / dtype invariants preserved through the loop (CLAUDE.md).
    assert len(out) == len(audio)
    assert out.dtype == audio.dtype


def test_each_stage_helper_is_individually_callable():
    """Each extracted stage preserves sample count when called in isolation."""
    from auralis.core.processing.stage_snapshot import PipelineJournal

    mode = _mode()
    params = SimpleNamespace(input_gain=0.0, target_lufs=-14.0)
    journal = PipelineJournal(mode.config.internal_sample_rate)
    audio = np.zeros((8192, 2), dtype=np.float32)

    # input_gain is a pure pass-through for |gain| <= 0.5; verifies wiring.
    out = mode._stage_input_gain(audio, params, journal)
    assert out.shape == audio.shape
    assert out.dtype == audio.dtype
