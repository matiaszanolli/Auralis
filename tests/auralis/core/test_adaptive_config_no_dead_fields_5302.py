"""AdaptiveConfig no longer carries seven fields nothing reads (#5302).

Sibling of #4613 (`critical_bands`). Each of these was declared, and
`parameter_smoothing` was even range-checked, but no code in `auralis/` or
`auralis-web/` ever read them, so `enable_psychoacoustic_eq=False` or
`enable_quality_monitoring=False` looked like a switch and did nothing.
"""

import dataclasses

import pytest

from auralis.core.config.settings import AdaptiveConfig
from auralis.core.config.unified_config import UnifiedConfig

_REMOVED = (
    "enable_tempo_analysis",
    "enable_energy_analysis",
    "parameter_smoothing",
    "enable_quality_monitoring",
    "auto_quality_adjustment",
    "min_quality_level",
    "enable_psychoacoustic_eq",
)


@pytest.mark.parametrize("name", _REMOVED)
def test_the_field_is_gone(name):
    assert name not in {f.name for f in dataclasses.fields(AdaptiveConfig)}


@pytest.mark.parametrize("name", _REMOVED)
def test_passing_it_fails_loudly_instead_of_being_ignored(name):
    with pytest.raises(TypeError):
        AdaptiveConfig(**{name: True})


def test_unified_config_still_round_trips():
    original = UnifiedConfig()
    rebuilt = UnifiedConfig.from_dict(original.to_dict())
    assert rebuilt.adaptive == original.adaptive
