"""
The default enhancement preset is defined once (#5794).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

VALID_PRESETS was the single source for which presets exist, but the *default*
was the string "adaptive" in 16 places (only ws_handlers/playback_commands had a
named constant). `schemas.DEFAULT_PRESET` is the one definition now. core/ keeps
its own local constant on purpose: it must not import schemas.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import re
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from schemas import DEFAULT_PRESET, VALID_PRESETS  # noqa: E402


def test_the_default_is_a_valid_preset():
    assert DEFAULT_PRESET in VALID_PRESETS


def test_the_ws_module_re_exports_the_schemas_constant():
    from ws_handlers import playback_commands

    assert playback_commands.DEFAULT_PRESET is DEFAULT_PRESET


@pytest.mark.parametrize(
    "rel",
    [
        "main.py",
        "helpers.py",
        "player_state.py",
        "routers/enhancement.py",
        "routers/processing_parameters.py",
        "routers/system.py",
        "routers/system_streams.py",
        "ws_handlers/connection.py",
        "ws_handlers/playback_commands.py",
        "cache/manager.py",
        "cache/playback_mixin.py",
    ],
)
def test_no_module_above_core_spells_the_default_as_a_literal(rel):
    code = "\n".join(
        line for line in (_BACKEND / rel).read_text().split("\n") if not line.lstrip().startswith("#")
    )
    assert not re.search(r"""(?:preset["']?\s*[:=,(]\s*|get\(["']preset["'],\s*)["']adaptive["']""", code), rel


def test_default_intensity_is_one_definition_in_schemas_and_in_range():
    """The default intensity is `schemas.DEFAULT_INTENSITY` and valid (#5982)."""
    from schemas import DEFAULT_INTENSITY, INTENSITY_MAX
    from ws_handlers import enhancement_params

    assert 0.0 <= DEFAULT_INTENSITY <= INTENSITY_MAX
    assert enhancement_params.DEFAULT_INTENSITY is DEFAULT_INTENSITY


@pytest.mark.parametrize(
    "rel",
    ["main.py", "helpers.py", "ws_handlers/connection.py", "services/recommendation_analysis.py",
     "routers/system_streams.py", "cache/manager.py", "cache/playback_mixin.py", "cache/status_mixin.py"],
)
def test_no_module_above_core_spells_the_default_intensity_as_a_literal(rel):
    code = "\n".join(
        line for line in (_BACKEND / rel).read_text().split("\n") if not line.lstrip().startswith("#")
    )
    assert not re.search(r"""intensity["']?(?::\s*float)?\s*[:=,(]\s*1\.0\b|get\(["']intensity["'],\s*1\.0\)""", code), rel
