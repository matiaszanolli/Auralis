"""
Stereo-width safety guards decide against unity, not a measurement (#4503/#4504)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`StereoWidthProcessor.apply_stereo_width_safe` asked "would this widen?" via
`target_width > current_width` — a width factor (side-gain axis, 0.5 = unity)
compared against a decorrelation measurement (0 = mono). Both live in 0..1 with
0.5 near the middle, so the comparison looked reasonable and was meaningless:
whether the clipping guard fired depended on how correlated the *material*
happened to be, not on what was being asked for.

Same defect in `AdaptiveMode._apply_stereo_width` and
`ContinuousMode._apply_stereo_width`.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import ast
import inspect
from pathlib import Path

import numpy as np
import pytest

from auralis.core.processing.base import StereoWidthProcessor
from auralis.dsp.utils.stereo import WIDTH_FACTOR_UNITY

SR = 44100


def _decorrelated(n: int = SR, seed: int = 0, amp: float = 0.05) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.stack(
        [rng.standard_normal(n), rng.standard_normal(n)], axis=1
    ).astype(np.float32) * amp


def _near_mono(n: int = SR, seed: int = 1, amp: float = 0.05) -> np.ndarray:
    audio = _decorrelated(n, seed, amp)
    audio[:, 1] = audio[:, 0] * 0.98
    return audio


def _side_gain(before: np.ndarray, after: np.ndarray) -> float:
    s0 = np.std((before[:, 0] - before[:, 1]) / 2.0)
    s1 = np.std((after[:, 0] - after[:, 1]) / 2.0)
    return float(s1 / s0) if s0 > 0 else float("nan")


class TestConservativeGuard:
    """"Skip widening when the peak is hot" must key on the request."""

    @pytest.mark.parametrize("audio_fn", [_decorrelated, _near_mono])
    def test_widening_is_skipped_when_peak_is_hot(self, audio_fn):
        audio = audio_fn()
        out = StereoWidthProcessor.apply_stereo_width_safe(
            audio, current_width=0.9, target_width=0.8, peak_db=4.0,
            safety_mode="conservative", sample_rate=SR,
        )
        assert out is audio, "hot-peak widening request was not skipped"

    @pytest.mark.parametrize("audio_fn", [_decorrelated, _near_mono])
    def test_narrowing_is_allowed_when_peak_is_hot(self, audio_fn):
        """Narrowing reduces peaks; the guard must not block it.

        Under the old comparison a narrowing request (factor 0.3) against a
        decorrelated source (reading 0.9) correctly proceeded, but against a
        near-mono source (reading 0.05) read as "widening" and was skipped.
        """
        audio = audio_fn()
        out = StereoWidthProcessor.apply_stereo_width_safe(
            audio, current_width=0.05, target_width=0.3, peak_db=4.0,
            safety_mode="conservative", sample_rate=SR,
        )
        assert out is not audio, "narrowing was wrongly skipped by the peak guard"
        assert _side_gain(audio, out) < 1.0

    def test_guard_outcome_does_not_depend_on_the_material(self):
        """The core regression: identical request, different material."""
        results = []
        for audio in (_decorrelated(seed=2), _near_mono(seed=3)):
            out = StereoWidthProcessor.apply_stereo_width_safe(
                audio, current_width=0.9, target_width=0.8, peak_db=4.0,
                safety_mode="conservative", sample_rate=SR,
            )
            results.append(out is audio)
        assert len(set(results)) == 1, (
            "the peak guard fired for one source and not the other, given the "
            "same width request — the decision is keying on the material"
        )


class TestAdaptiveClamp:
    def test_expansion_clamp_is_relative_to_unity(self):
        audio = _decorrelated(amp=0.02)
        out = StereoWidthProcessor.apply_stereo_width_safe(
            audio, current_width=0.05, target_width=5.0, peak_db=4.0,
            safety_mode="adaptive", sample_rate=SR,
        )
        # Clamped to UNITY + 0.6 = 1.1 -> side gain 2.2, not 10.0.
        assert _side_gain(audio, out) == pytest.approx(2.2, rel=0.15)

    def test_clamp_ceiling_is_independent_of_the_measurement(self):
        audio = _decorrelated(amp=0.02, seed=4)
        gains = []
        for reading in (0.0, 0.5, 1.0):
            out = StereoWidthProcessor.apply_stereo_width_safe(
                audio, current_width=reading, target_width=5.0, peak_db=4.0,
                safety_mode="adaptive", sample_rate=SR,
            )
            gains.append(_side_gain(audio, out))
        assert max(gains) - min(gains) < 1e-6, (
            f"clamp ceiling moved with the decorrelation reading: {gains}"
        )


class TestApplyThreshold:
    def test_near_unity_request_is_a_no_op(self):
        audio = _decorrelated(seed=5)
        out = StereoWidthProcessor.apply_stereo_width_safe(
            audio, current_width=0.9, target_width=WIDTH_FACTOR_UNITY + 0.05,
            peak_db=-10.0, safety_mode="adaptive", sample_rate=SR,
        )
        assert out is audio

    def test_meaningful_request_is_applied(self):
        audio = _decorrelated(seed=6)
        out = StereoWidthProcessor.apply_stereo_width_safe(
            audio, current_width=0.9, target_width=0.8,
            peak_db=-10.0, safety_mode="adaptive", sample_rate=SR,
        )
        assert out is not audio
        assert _side_gain(audio, out) > 1.0


class TestNoCrossScaleComparisonsRemain:
    """AST guard: no processor may compare a width factor to a measurement."""

    MODULES = [
        "auralis/core/processing/continuous_mode.py",
        "auralis/core/processing/adaptive_mode.py",
        "auralis/core/processing/base/stereo_width_processor.py",
    ]

    @pytest.mark.parametrize("relpath", MODULES)
    def test_no_target_vs_current_width_comparison(self, relpath: str):
        root = Path(__file__).resolve().parents[3]
        tree = ast.parse((root / relpath).read_text())

        measurement_names = {"current_width", "current_decorrelation", "pre_decorrelation"}
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            if "target_width" in names and names & measurement_names:
                offenders.append(node.lineno)
        assert not offenders, (
            f"{relpath}: width factor compared against a decorrelation "
            f"measurement at line(s) {offenders} — different axes (#4503)"
        )

    @pytest.mark.parametrize("relpath", MODULES)
    def test_full_band_widening_is_not_used(self, relpath: str):
        """Continuous/adaptive paths must route through the multiband version.

        Full-band `adjust_stereo_width` applies one mid/side gain across the
        whole spectrum, widening kick and bass with everything else (#4504).
        """
        root = Path(__file__).resolve().parents[3]
        tree = ast.parse((root / relpath).read_text())
        called = {
            n.func.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "adjust_stereo_width" not in called, (
            f"{relpath} calls full-band adjust_stereo_width; use "
            "adjust_stereo_width_multiband so sub-300 Hz stays centred (#4504)"
        )


class TestSignature:
    def test_apply_stereo_width_safe_accepts_sample_rate(self):
        """The multiband crossovers need it; a wrong rate misplaces the bands.

        #4622: sample_rate has no default any more — a silent 44.1kHz
        fallback is exactly the hazard that issue removed. A caller must
        pass the real rate explicitly.
        """
        params = inspect.signature(
            StereoWidthProcessor.apply_stereo_width_safe
        ).parameters
        assert "sample_rate" in params
        assert params["sample_rate"].default is inspect.Parameter.empty
