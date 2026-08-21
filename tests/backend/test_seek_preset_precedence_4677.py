"""`seek` and `play_enhanced` resolve preset/intensity by the same rule (#4677).

The two handlers used to apply *opposite* precedence to the same two
quantities:

* ``handle_play_enhanced`` validated the client value against
  ``VALID_PRESETS`` and treated it as authoritative, falling back to the
  stored settings dict only for what the payload omitted;
* ``handle_seek`` did the reverse — ``preset = settings.get("preset", preset)``
  over a dict that *always* carries a ``"preset"`` key, so a seek frame's own
  preset was discarded unconditionally — and skipped the ``VALID_PRESETS``
  check entirely, so in the branch where no settings dict exists the raw
  client string reached processor construction unvalidated.

Both now route through ``resolve_enhancement_params``. The client payload wins
when valid; each fallback mapping is consulted in order for the rest.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.audio_stream_controller import ws_id as _ws_id  # noqa: E402
from ws_handlers import playback_commands  # noqa: E402
from ws_handlers.context import StreamState, WSDeps  # noqa: E402
from ws_handlers.playback_commands import (  # noqa: E402
    DEFAULT_INTENSITY,
    DEFAULT_PRESET,
    handle_play_enhanced,
    handle_seek,
    resolve_enhancement_params,
)


def _ws():
    websocket = MagicMock()
    websocket.send_text = AsyncMock()
    websocket.client_state = MagicMock()
    websocket.client_state.name = "CONNECTED"
    return websocket


def _state():
    return StreamState(
        active_tasks={},
        active_tasks_lock=asyncio.Lock(),
        active_track_ids={},
        pause_events={},
        flow_events={},
    )


def _deps(settings, *, stream_from_position=None, stream_audio=None):
    return WSDeps(
        get_repository_factory=None,
        get_enhancement_settings=(lambda: settings) if settings is not None else None,
        get_cache_manager=None,
        get_processing_engine=MagicMock(),
        stream_audio=stream_audio or AsyncMock(),
        stream_normal=AsyncMock(),
        stream_from_position=stream_from_position or AsyncMock(),
        broadcast_manager=None,
    )


async def _run_seek(websocket, data, state, deps):
    """Dispatch a seek and return the kwargs its stream task was started with.

    The handler launches ``stream_from_position`` as a background task, so the
    call is only recorded once that task has been awaited.
    """
    calls: list[dict] = []

    async def recorder(*_args, **kwargs):
        calls.append(kwargs)

    deps.stream_from_position = recorder
    await handle_seek(websocket, {"data": data}, state, deps)
    task = state.active_tasks.get(_ws_id(websocket))
    if task is not None:
        await task
    return calls[0] if calls else None


async def _run_play(websocket, data, state, deps):
    """Same, for ``play_enhanced``/``stream_audio``."""
    calls: list[dict] = []

    async def recorder(*_args, **kwargs):
        calls.append(kwargs)

    deps.stream_audio = recorder
    await handle_play_enhanced(websocket, {"data": data}, state, deps)
    task = state.active_tasks.get(_ws_id(websocket))
    if task is not None:
        await task
    return calls[0] if calls else None


# ---------------------------------------------------------------------------
# resolve_enhancement_params — the shared rule, in isolation
# ---------------------------------------------------------------------------

class TestResolver:
    def test_valid_client_value_beats_every_fallback(self):
        preset, intensity = resolve_enhancement_params(
            {"preset": "warm", "intensity": 0.25},
            {"preset": "gentle", "intensity": 0.9},
            {"preset": "punchy", "intensity": 0.1},
        )
        assert preset == "warm"
        assert intensity == 0.25

    def test_fallbacks_are_consulted_in_order(self):
        preset, intensity = resolve_enhancement_params(
            {},
            {"preset": "gentle", "intensity": 0.9},
            {"preset": "punchy", "intensity": 0.1},
        )
        assert preset == "gentle"
        assert intensity == 0.9

    def test_a_later_fallback_supplies_what_an_earlier_one_lacks(self):
        preset, intensity = resolve_enhancement_params(
            {},
            {"intensity": 0.9},
            {"preset": "punchy", "intensity": 0.1},
        )
        assert preset == "punchy"
        assert intensity == 0.9

    def test_none_fallbacks_are_skipped_not_treated_as_empty(self):
        preset, intensity = resolve_enhancement_params(
            {}, None, {"preset": "bright", "intensity": 0.4}
        )
        assert preset == "bright"
        assert intensity == 0.4

    def test_invalid_client_preset_is_rejected_and_falls_through(self):
        preset, _ = resolve_enhancement_params(
            {"preset": "notapreset"}, {"preset": "gentle"}
        )
        assert preset == "gentle"

    def test_an_off_list_stored_preset_is_rejected_too(self):
        # `default_preset` is a plain String column, so a legacy or
        # hand-edited row can seed garbage into the runtime dict.
        preset, _ = resolve_enhancement_params({}, {"preset": "legacy-v1"})
        assert preset is None

    def test_preset_is_case_insensitive(self):
        preset, _ = resolve_enhancement_params({"preset": "WaRm"})
        assert preset == "warm"

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 2.0, "0.5", True])
    def test_invalid_intensity_is_rejected(self, bad):
        _, intensity = resolve_enhancement_params({"intensity": bad})
        assert intensity is None

    def test_nothing_resolvable_returns_none_not_a_default(self):
        # The caller chooses between erroring and defaulting; the resolver
        # never makes that call for it.
        assert resolve_enhancement_params({}) == (None, None)


# ---------------------------------------------------------------------------
# handle_seek — the acceptance criteria
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSeek:
    async def test_seek_carrying_a_preset_streams_with_it(self):
        """AC 1: the client value is no longer discarded."""
        state = _state()
        websocket = _ws()
        state.active_stream_settings[_ws_id(websocket)] = {
            "preset": "adaptive", "intensity": 1.0, "enabled": True
        }
        deps = _deps({"enabled": True, "preset": "adaptive", "intensity": 1.0})

        kwargs = await _run_seek(
            websocket, {"track_id": 1, "position": 30, "preset": "warm"}, state, deps
        )
        assert kwargs["preset"] == "warm"

    async def test_seek_carrying_an_invalid_preset_does_not_pass_it_through(self):
        """AC 2: an off-list value falls back rather than reaching the processor."""
        state = _state()
        websocket = _ws()
        state.active_stream_settings[_ws_id(websocket)] = {
            "preset": "gentle", "intensity": 1.0, "enabled": True
        }
        deps = _deps({"enabled": True, "preset": "adaptive", "intensity": 1.0})

        kwargs = await _run_seek(
            websocket,
            {"track_id": 1, "position": 30, "preset": "notapreset"},
            state,
            deps,
        )
        assert kwargs["preset"] == "gentle"

    async def test_invalid_preset_with_no_settings_source_defaults_rather_than_leaking(self):
        """The branch that used to forward the raw string unvalidated.

        With `get_enhancement_settings` unset and no recorded stream there is
        nothing to fall back to, so the module default applies — the one thing
        that must not happen is the client's string reaching the processor.
        """
        state = _state()
        websocket = _ws()
        deps = _deps(None)

        kwargs = await _run_seek(
            websocket,
            {"track_id": 1, "position": 30, "preset": "'; DROP TABLE tracks;--"},
            state,
            deps,
        )
        assert kwargs["preset"] == DEFAULT_PRESET
        assert kwargs["intensity"] == DEFAULT_INTENSITY

    async def test_omitted_preset_still_inherits_this_connections_stream(self):
        """#4742 must survive: the per-connection snapshot beats the global."""
        state = _state()
        websocket = _ws()
        state.active_stream_settings[_ws_id(websocket)] = {
            "preset": "bright", "intensity": 0.3, "enabled": True
        }
        deps = _deps({"enabled": True, "preset": "punchy", "intensity": 0.9})

        kwargs = await _run_seek(websocket, {"track_id": 1, "position": 30}, state, deps)
        assert kwargs["preset"] == "bright"
        assert kwargs["intensity"] == 0.3

    async def test_omitted_preset_falls_back_to_the_global_without_a_recorded_stream(self):
        state = _state()
        websocket = _ws()
        deps = _deps({"enabled": True, "preset": "punchy", "intensity": 0.9})

        kwargs = await _run_seek(websocket, {"track_id": 1, "position": 30}, state, deps)
        assert kwargs["preset"] == "punchy"
        assert kwargs["intensity"] == 0.9

    async def test_client_intensity_wins_over_the_recorded_stream(self):
        state = _state()
        websocket = _ws()
        state.active_stream_settings[_ws_id(websocket)] = {
            "preset": "warm", "intensity": 1.0, "enabled": True
        }
        deps = _deps({"enabled": True, "preset": "warm", "intensity": 1.0})

        kwargs = await _run_seek(
            websocket,
            {"track_id": 1, "position": 30, "intensity": 0.25},
            state,
            deps,
        )
        assert kwargs["intensity"] == 0.25

    async def test_enabled_still_comes_from_the_live_global_not_the_snapshot(self):
        """#5075 must survive: only preset/intensity use the snapshot."""
        state = _state()
        websocket = _ws()
        state.active_stream_settings[_ws_id(websocket)] = {
            "preset": "warm", "intensity": 1.0, "enabled": True
        }
        deps = _deps({"enabled": False, "preset": "warm", "intensity": 1.0})

        kwargs = await _run_seek(websocket, {"track_id": 1, "position": 30}, state, deps)
        assert kwargs["enhancement_enabled"] is False


# ---------------------------------------------------------------------------
# handle_play_enhanced — AC 3: behaviour unchanged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPlayEnhancedUnchanged:
    async def test_client_preset_still_wins(self):
        state = _state()
        websocket = _ws()
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
        deps = _deps(settings)

        kwargs = await _run_play(
            websocket,
            {"track_id": 1, "preset": "warm", "intensity": 0.5},
            state,
            deps,
        )
        assert kwargs["preset"] == "warm"
        assert kwargs["intensity"] == 0.5
        # The #4601 write-back still records the accepted values.
        assert settings["preset"] == "warm"
        assert settings["intensity"] == 0.5

    async def test_omitted_preset_still_falls_back_to_the_stored_dict(self):
        state = _state()
        websocket = _ws()
        deps = _deps({"enabled": True, "preset": "gentle", "intensity": 0.7})

        kwargs = await _run_play(websocket, {"track_id": 1}, state, deps)
        assert kwargs["preset"] == "gentle"
        assert kwargs["intensity"] == 0.7

    async def test_invalid_preset_with_no_settings_source_still_errors(self):
        """play_enhanced deliberately does NOT degrade the way seek does."""
        state = _state()
        websocket = _ws()
        deps = _deps(None, stream_audio=AsyncMock())

        await handle_play_enhanced(
            websocket, {"data": {"track_id": 1, "preset": "notapreset"}}, state, deps
        )
        assert state.active_tasks == {}
        deps.stream_audio.assert_not_called()
        sent = "".join(c.args[0] for c in websocket.send_text.call_args_list)
        assert "invalid_preset" in sent


# ---------------------------------------------------------------------------
# WIRING
# ---------------------------------------------------------------------------

def test_no_handler_open_codes_the_resolution_any_more():
    """Both handlers go through the helper — a re-divergence would show here."""
    source = Path(playback_commands.__file__).read_text()
    # Comments quote the old expressions verbatim to explain what changed, so
    # strip them — otherwise this asserts against the explanation, not the code.
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    body = code.split("async def handle_play_enhanced", 1)[1]
    assert 'settings.get("preset"' not in body
    assert 'settings.get("intensity"' not in body
    assert body.count("resolve_enhancement_params(") == 2
