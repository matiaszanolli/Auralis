"""
Module-boundary guard for the continuous-mode split (#4254)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#4082 split `ContinuousMode.process()` and #4254's first pass split
`_apply_dsp_stages`, but both times the complexity moved *within*
`continuous_mode.py` rather than out of it — the file went 743 -> 802 -> 789
lines while two issues were closed against it. #4673 made "target file verified
under the 300-line convention" the acceptance criterion precisely because a
method-level split reads as done while the file it lives in keeps growing.

These tests pin the outcome rather than the process: every module the split
produced stays inside the convention, and the four responsibilities stay in
separate files instead of drifting back together.
"""

from pathlib import Path

import pytest

# CLAUDE.md, Principles #2: "< 300 lines per module, single responsibility".
MAX_MODULE_LINES = 300

_PROCESSING = Path(__file__).resolve().parents[3] / "auralis" / "core" / "processing"

SPLIT_MODULES = [
    "continuous_mode.py",       # parameter resolution — the orchestrator
    "continuous_stages.py",     # the guarded DSP stage sequence
    "continuous_dsp_ops.py",    # the DSP primitives the stages drive
    "continuous_guards.py",     # guard knees and their two helpers
    "continuous_quality.py",    # advisory before/after measurement
    "fixed_target_params.py",   # fixed-targets dict -> ProcessingParameters
]


@pytest.mark.parametrize("module_name", SPLIT_MODULES)
def test_split_module_respects_the_line_convention(module_name: str) -> None:
    path = _PROCESSING / module_name
    assert path.exists(), f"{module_name} is missing — did the #4254 split get reverted?"

    line_count = len(path.read_text().splitlines())
    assert line_count <= MAX_MODULE_LINES, (
        f"{module_name} is {line_count} lines, over the {MAX_MODULE_LINES}-line "
        "convention. Extract the new responsibility into its own module rather "
        "than growing this one (#4254 / #4673)."
    )


def test_continuous_mode_delegates_rather_than_defining_the_pipeline() -> None:
    """The class file must not re-absorb the stage sequence or the primitives."""
    source = (_PROCESSING / "continuous_mode.py").read_text()
    for method in ("def _apply_dsp_stages", "def _stage_", "def _apply_eq",
                   "def _apply_dynamics", "def _apply_stereo_width",
                   "def _apply_final_normalization", "def _record_quality_measurements"):
        assert method not in source, (
            f"'{method}' is back in continuous_mode.py — it belongs in "
            "continuous_stages.py / continuous_dsp_ops.py / "
            "continuous_quality.py (#4254)"
        )


def test_the_composed_class_still_exposes_every_moved_method() -> None:
    """Splitting into mixins must not change ContinuousMode's own surface."""
    from auralis.core.processing.continuous_mode import ContinuousMode

    for method in ("_apply_dsp_stages", "_stage_input_gain", "_stage_eq",
                   "_stage_dynamics", "_stage_stereo_width", "_stage_normalization",
                   "_record_quality_measurements", "_apply_eq", "_apply_dynamics",
                   "_apply_compression", "_apply_expansion", "_apply_stereo_width",
                   "_apply_final_normalization"):
        assert callable(getattr(ContinuousMode, method, None)), method
