"""
NormalizationStep.log_summary diagnostics — issue #4391
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`crest_delta` was computed and then never printed, so `ruff --select F841`
reported it as an unused local. The tempting fix — deleting the binding — would
have silently confirmed the missing diagnostic instead of repairing it: the
branch's own comment calls itself "RMS/Crest-based logging", the sibling
`peak_delta`/`rms_delta` are both printed, and crest crush is the thing the
adaptive path's guards actually act on.

These tests pin the summary's content so a future `ruff --fix` pass cannot quietly
drop the measurement again, and so the two branches stay distinguishable.
"""

import numpy as np
import pytest

from auralis.core.processing.base import NormalizationStep


def _audio(peak: float = 0.5, length: int = 4096) -> np.ndarray:
    """A signal with a known peak and a crest factor well above 0 dB."""
    rng = np.random.default_rng(1234)
    audio = rng.standard_normal((length, 2)).astype(np.float32) * (peak / 6.0)
    audio[0, :] = peak  # pin the peak so crest is comfortably positive
    return audio


@pytest.fixture
def step() -> NormalizationStep:
    return NormalizationStep("Test Gain", stage_label="Pre-Final")


class TestAdaptiveBranchSummary:
    """The RMS/Crest branch — the one `adaptive_mode.py` actually reaches."""

    def _summary(self, step: NormalizationStep, capsys) -> str:
        step.measure_before(_audio(peak=0.5))
        step.measure_after(_audio(peak=0.25))
        capsys.readouterr()  # discard anything the measure_* calls emitted
        step.log_summary()
        return capsys.readouterr().out

    def test_reports_all_three_measurements(self, step, capsys):
        out = self._summary(step, capsys)
        for label in ("Peak:", "RMS:", "Crest:"):
            assert label in out, f"{label} missing from the summary (#4391)"

    def test_reports_a_signed_crest_delta(self, step, capsys):
        """The delta, not just the endpoints — that is what F841 flagged."""
        out = self._summary(step, capsys)
        crest_section = out.split("Crest:", 1)[1]
        assert "Δ" in crest_section
        assert ("+" in crest_section) or ("-" in crest_section)

    def test_crest_delta_equals_peak_delta_minus_rms_delta(self, step, capsys):
        """crest = peak_db - rms_db, so the printed deltas must be consistent."""
        out = self._summary(step, capsys)
        deltas = [float(part.split(")")[0]) for part in out.split("Δ ")[1:]]
        peak_delta, rms_delta, crest_delta = deltas
        assert crest_delta == pytest.approx(peak_delta - rms_delta, abs=0.02)

    def test_summary_is_silent_until_both_measurements_exist(self, step, capsys):
        capsys.readouterr()
        step.log_summary()
        assert capsys.readouterr().out == ""

        step.measure_before(_audio())
        capsys.readouterr()
        step.log_summary()
        assert capsys.readouterr().out == "", "before-only must not log a summary"


class TestLufsBranchSummary:
    """The continuous-mode branch reports LUFS instead, and stays that way."""

    def test_lufs_branch_reports_lufs_and_peak(self, step, capsys):
        step.measure_before(_audio(peak=0.5), use_lufs=True, sample_rate=44100)
        step.measure_after(_audio(peak=0.25), use_lufs=True, sample_rate=44100)
        capsys.readouterr()
        step.log_summary()
        out = capsys.readouterr().out

        assert "LUFS:" in out
        assert "Peak:" in out
        # Crest belongs to the adaptive branch; adding it here would change what
        # the continuous-mode logs mean.
        assert "Crest:" not in out
