"""Dead stereo-width measurements stay removed from the DSP API (#5235)."""

import inspect

from auralis.core.stages import stereo_expansion
from auralis.core.simple_mastering import SimpleMasteringPipeline
from auralis.dsp.utils.stereo import adjust_stereo_width_multiband


def test_multiband_width_api_contains_only_active_inputs() -> None:
    assert tuple(inspect.signature(adjust_stereo_width_multiband).parameters) == (
        "stereo_audio",
        "width_factor",
        "sample_rate",
    )


def test_stage_no_longer_accepts_unused_bass_measurement() -> None:
    parameters = inspect.signature(stereo_expansion.apply).parameters
    assert "bass_pct" not in parameters
    assert "current_width" in parameters

    wrapper_parameters = inspect.signature(
        SimpleMasteringPipeline._apply_stereo_expansion
    ).parameters
    assert "bass_pct" not in wrapper_parameters
