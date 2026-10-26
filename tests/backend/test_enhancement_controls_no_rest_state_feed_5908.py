"""Enhancement setting changes no longer feed look-ahead from REST player state (#5908).

`_maybe_prewarm_upcoming_chunks` and both `update_position()` calls in the
enhancement controls read `player_state_manager.get_state()`. The frontend plays
through WebSocket `play_*` and never calls `/api/player/play` or `/load`, so
that state is stale or empty: the prewarm gate almost never opened, and when it
did it skipped any track with a live WS stream (#5323); the cache worker was fed
a stale position for a track that might not be playing. The live stream the
frontend re-issues after each settings POST renders the upcoming chunks itself,
so the feed is gone rather than rewired.
"""

import importlib
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from cache.manager import StreamlinedCacheManager  # noqa: E402
from routers import enhancement_controls  # noqa: E402

HANDLERS = ("toggle_enhancement", "set_enhancement_preset", "set_enhancement_intensity")
STALE_STATE_DEPS = {"player_state_manager", "buffer_manager"}


@pytest.mark.parametrize("name", HANDLERS)
def test_handlers_do_not_depend_on_rest_player_state(name):
    params = set(inspect.signature(getattr(enhancement_controls, name)).parameters)

    assert not params & STALE_STATE_DEPS


def test_controls_never_touch_the_cache_manager_position_feed():
    source = inspect.getsource(enhancement_controls)

    assert "update_position" not in source
    assert "get_state()" not in source


def test_the_prewarm_module_is_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("routers.enhancement_prewarm")


def test_cache_manager_has_no_unwritten_auto_mastering_flag():
    assert not hasattr(StreamlinedCacheManager(), "auto_mastering_enabled")
