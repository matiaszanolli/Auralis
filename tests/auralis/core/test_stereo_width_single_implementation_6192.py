"""Stereo-width gating has exactly one implementation (#6192).

The #5108 smooth-gate fix originally reached only the continuous copy:
`AdaptiveMode._apply_stereo_width` kept a hard ``input_level > 0.8`` clamp,
the helper's own ``peak_db > 3.0`` branch could never fire for normalised
float audio, and `ContinuousDSPOpsMixin._apply_stereo_width` was a third
implementation. A fix to stereo-widening safety had to be made in three
places and was made in one.

Now `StereoWidthProcessor.apply_stereo_width_safe` is the single
implementation and both modes call it, so the two modes widen identically.
"""

import ast
import importlib
import inspect
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from auralis.core.processing.base import StereoWidthProcessor
from auralis.core.processing.continuous_guards import (
    WIDTH_PEAK_KNEE_END,
    WIDTH_PEAK_KNEE_START,
)
from auralis.dsp.utils.stereo import stereo_width_analysis

SR = 44100

_ROOT = Path(__file__).resolve().parents[3]


def _decorrelated_stereo(peak: float = 0.1, n: int = 8192, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    left = rng.standard_normal(n)
    right = 0.6 * left + 0.4 * rng.standard_normal(n)
    stereo = np.stack([left, right], axis=1).astype(np.float32)
    stereo /= np.max(np.abs(stereo))
    return (stereo * peak).astype(np.float32)


def _applied_width(audio: np.ndarray, target_width: float, peak_db: float) -> float:
    """The width factor the helper actually applied, read off the output."""
    out = StereoWidthProcessor.apply_stereo_width_safe(
        audio, current_width=stereo_width_analysis(audio), target_width=target_width,
        peak_db=peak_db, sample_rate=SR,
    )
    # The multiband adjuster scales side by (2 * width); recover it.
    before = np.std((audio[:, 0] - audio[:, 1]) / 2.0)
    after = np.std((out[:, 0] - out[:, 1]) / 2.0)
    return float(after / before) / 2.0 if before > 0 else float("nan")


class TestHelperKneeIsContinuous:
    def test_width_changes_continuously_across_the_knee(self):
        """Sweeping the peak across the #5108 knee moves the applied width
        smoothly — the helper carries the ramp, no hard switch remains."""
        widen = 0.8
        peaks = np.arange(-6.0, 0.0, 0.05)
        widths = np.array(
            [_applied_width(_decorrelated_stereo(), widen, float(p)) for p in peaks]
        )
        steps = np.abs(np.diff(widths))
        assert steps.max() < 0.02, (
            f"applied width jumped {steps.max():.4f} between adjacent 0.05 dB "
            f"peaks near {peaks[int(np.argmax(steps))]:.2f} dB"
        )

    def test_output_length_equals_input_length(self):
        audio = _decorrelated_stereo()
        out = StereoWidthProcessor.apply_stereo_width_safe(
            audio, current_width=0.5, target_width=0.8, peak_db=-12.0,
            sample_rate=SR,
        )
        assert out.shape == audio.shape
        assert out.dtype == audio.dtype


class TestBothModesWidenIdentically:
    """AdaptiveMode and ContinuousDSPOpsMixin must produce the same output
    for the same input and target — they run the same helper (#6192)."""

    @staticmethod
    def _run_adaptive(audio, target_width):
        from auralis.core.processing.adaptive_mode import AdaptiveMode

        stub = SimpleNamespace(config=SimpleNamespace(internal_sample_rate=SR))
        targets = {"stereo_width": target_width}
        return AdaptiveMode._apply_stereo_width(stub, audio, targets)

    @staticmethod
    def _run_continuous(audio, target_width):
        from auralis.core.processing.continuous_dsp_ops import ContinuousDSPOpsMixin

        stub = SimpleNamespace(config=SimpleNamespace(internal_sample_rate=SR))
        params = SimpleNamespace(stereo_width_target=target_width)
        return ContinuousDSPOpsMixin._apply_stereo_width(stub, audio, params)

    @pytest.mark.parametrize("peak", [0.05, 0.5, 0.9])
    def test_identical_output_for_identical_input(self, peak):
        audio = _decorrelated_stereo(peak=peak)
        np.testing.assert_array_equal(
            self._run_adaptive(audio, 0.8), self._run_continuous(audio, 0.8)
        )

    def test_narrowing_matches_too(self):
        audio = _decorrelated_stereo(peak=0.5)
        np.testing.assert_array_equal(
            self._run_adaptive(audio, 0.3), self._run_continuous(audio, 0.3)
        )


class TestSingleImplementation:
    """Structural guards: the deleted hard strategies stay deleted."""

    @pytest.mark.parametrize("relpath", [
        "auralis/core/processing/adaptive_mode.py",
        "auralis/core/processing/continuous_dsp_ops.py",
        "auralis/core/processing/base/stereo_width_processor.py",
    ])
    def test_no_hard_peak_switches(self, relpath):
        """The hard gates (#5108 removed, #6192 consolidated) must not return:
        no `input_level > <number>` and no bare `peak_db > <number>` Compare."""
        tree = ast.parse((_ROOT / relpath).read_text())
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            literals = {
                n.value for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            }
            if "input_level" in names and literals:
                offenders.append(node.lineno)
            if "peak_db" in names and literals:
                offenders.append(node.lineno)
        assert not offenders, (
            f"{relpath}: hard peak switch at line(s) {offenders} — the "
            "smooth_gate knee in apply_stereo_width_safe is the only gate"
        )

    def test_helper_carries_the_knee(self):
        """The single knee lives in the helper, not in a stage method."""
        from auralis.core.processing.base import stereo_width_processor

        src = inspect.getsource(stereo_width_processor)
        assert "smooth_gate" in src
        for stage_module in (
            "auralis.core.processing.adaptive_mode",
            "auralis.core.processing.continuous_dsp_ops",
        ):
            stage_src = inspect.getsource(importlib.import_module(stage_module))
            assert "WIDTH_PEAK_KNEE" not in stage_src, stage_module

    def test_knee_constants_are_importable_from_the_helper_module(self):
        assert WIDTH_PEAK_KNEE_START < WIDTH_PEAK_KNEE_END
