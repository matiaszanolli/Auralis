"""
Regression tests for the enhancement router's closure-to-module-level
extraction (#4670).

create_enhancement_router() used to be a ~380-line closure -- every handler
was a nested `async def` reachable only by constructing the whole router
with its full dependency graph. Handlers are now module-level `async def`
functions with FastAPI Depends() defaults; a caller that wants to unit-test
one directly just passes the dependency explicitly as a keyword argument,
bypassing Depends() (and _EnhancementDeps, and the router) entirely.
These tests exist to prove that seam is real, not just that it types.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.enhancement import (  # noqa: E402
    SetIntensityRequest,
    SetPresetRequest,
    ToggleEnhancementRequest,
    get_enhancement_status,
    set_enhancement_intensity,
    set_enhancement_preset,
    toggle_enhancement,
)

pytestmark = pytest.mark.asyncio


def _connection_manager():
    cm = MagicMock()
    cm.broadcast = AsyncMock()
    return cm


async def test_get_enhancement_status_callable_with_a_bare_settings_dict():
    """No router, no _EnhancementDeps, no app -- just the handler and a dict."""
    settings = {"enabled": True, "preset": "warm", "intensity": 0.5}

    result = await get_enhancement_status(enhancement_settings=settings)

    assert result is settings


async def test_toggle_enhancement_callable_with_bare_stubs():
    settings = {"enabled": False, "preset": "adaptive", "intensity": 1.0}
    cm = _connection_manager()

    result = await toggle_enhancement(
        ToggleEnhancementRequest(enabled=True),
        enhancement_settings=settings,
        player_state_manager=None,
        connection_manager=cm,
    )

    # The runtime settings dict is shared by reference and mutated in place
    # (#4409) -- the extraction must not have turned it into a copy.
    assert settings["enabled"] is True
    assert result["settings"] is settings
    cm.broadcast.assert_awaited_once()
    assert cm.broadcast.await_args[0][0]["type"] == "enhancement_settings_changed"


async def test_set_enhancement_preset_notifies_the_buffer_manager():
    """The multi-tier buffer + state manager are passed in directly here --
    the branch-prediction call the old closure reached via get_multi_tier_buffer()."""
    settings = {"enabled": True, "preset": "adaptive", "intensity": 0.7}
    cm = _connection_manager()

    buffer_manager = MagicMock()
    buffer_manager.update_position = AsyncMock()

    state = MagicMock()
    state.current_track.id = 7
    state.current_time = 12.5
    player_state_manager = MagicMock()
    player_state_manager.get_state = MagicMock(return_value=state)

    result = await set_enhancement_preset(
        SetPresetRequest(preset="WARM"),  # lowercased by the request model
        enhancement_settings=settings,
        buffer_manager=buffer_manager,
        player_state_manager=player_state_manager,
        connection_manager=cm,
    )

    assert settings["preset"] == "warm"
    assert result["message"] == "Preset changed to warm"
    buffer_manager.update_position.assert_awaited_once_with(
        track_id=7, position=12.5, preset="warm", intensity=0.7
    )


async def test_set_enhancement_intensity_skips_buffer_when_unwired():
    """With no buffer manager (the optional dependency resolving to None),
    the handler still mutates + broadcasts rather than raising."""
    settings = {"enabled": True, "preset": "bright", "intensity": 1.0}
    cm = _connection_manager()

    result = await set_enhancement_intensity(
        SetIntensityRequest(intensity=0.25),
        enhancement_settings=settings,
        buffer_manager=None,
        player_state_manager=None,
        connection_manager=cm,
    )

    assert settings["intensity"] == 0.25
    assert result["settings"] is settings
    assert cm.broadcast.await_args[0][0]["data"]["intensity"] == 0.25
