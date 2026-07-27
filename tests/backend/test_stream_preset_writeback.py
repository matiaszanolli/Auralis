"""The accepted streaming preset is recorded, not just used (#4601).

`handle_play_enhanced` treats the WS payload as authoritative for
`preset`/`intensity` and falls back to the stored setting only when the payload
omits or fails to validate them — but it never wrote the accepted values back
into `enhancement_settings`. Two readers key off that global and went silently
wrong whenever the two diverged:

* ``GET /api/processing/parameters`` resolves the content profile from the
  global preset, but ``_last_content_profiles`` is written by the running
  ``ChunkedAudioProcessor`` under the STREAM's preset. A miss returns hardcoded
  ``is_default: True`` placeholders — the visualiser reads as "nothing is
  happening" while processing is in fact under way, which is worse than a blank
  panel.
* ``_preprocess_upcoming_chunks`` pre-warms cache entries for the global
  preset/intensity, so every pre-warmed chunk missed.

The normal UI path keeps the two aligned only by convention (``setPreset`` POSTs
before re-issuing the stream); the `force` path from #3773 exists precisely to
bypass that round-trip, which is what makes the divergence reachable.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from ws_handlers.playback_commands import handle_play_enhanced  # noqa: E402

pytestmark = pytest.mark.asyncio


def _deps(settings: dict):
    """Minimal deps object: enough to reach the settings resolution."""
    deps = MagicMock()
    deps.get_enhancement_settings = lambda: settings
    # The handler fires the stream as a background task; a no-op coroutine keeps
    # the test to the settings-resolution path it is about.
    deps.stream_audio = AsyncMock()
    return deps


def _ws():
    ws = MagicMock()
    ws.send_text = AsyncMock()
    ws.client_state = MagicMock()
    ws.client_state.name = "CONNECTED"
    return ws


def _state():
    import asyncio as _asyncio

    from ws_handlers.context import StreamState

    return StreamState(
        active_tasks={},
        active_tasks_lock=_asyncio.Lock(),
        active_track_ids={},
        pause_events={},
        flow_events={},
    )


async def _run(settings: dict, payload: dict):
    deps = _deps(settings)
    message = {"type": "play_enhanced", "data": {"track_id": 1, **payload}}
    await handle_play_enhanced(_ws(), message, _state(), deps)
    return settings


class TestAcceptedValuesAreRecorded:
    async def test_payload_preset_is_written_back(self):
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}

        await _run(settings, {"preset": "warm"})

        assert settings["preset"] == "warm", (
            "the stream runs on 'warm' but the global still said 'adaptive', so "
            "/api/processing/parameters looked up a key nothing was writing (#4601)"
        )

    async def test_payload_intensity_is_written_back(self):
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}

        await _run(settings, {"preset": "warm", "intensity": 0.3})

        assert settings["intensity"] == 0.3

    async def test_the_settings_dict_is_mutated_in_place(self):
        """Rebinding would be invisible to the routers that share it (#4409)."""
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
        same_object = settings

        await _run(settings, {"preset": "punchy"})

        assert same_object is settings
        assert same_object["preset"] == "punchy"


class TestFallbacksUnchanged:
    async def test_omitted_preset_keeps_the_stored_one(self):
        settings = {"enabled": True, "preset": "gentle", "intensity": 0.8}

        await _run(settings, {})

        assert settings["preset"] == "gentle"
        assert settings["intensity"] == 0.8

    async def test_invalid_preset_falls_back_without_corrupting_the_global(self):
        settings = {"enabled": True, "preset": "gentle", "intensity": 0.8}

        await _run(settings, {"preset": "not-a-preset"})

        assert settings["preset"] == "gentle"

    @pytest.mark.parametrize("bad", [1.5, -0.2, float("nan"), float("inf"), "0.5", None])
    async def test_invalid_intensity_falls_back_without_corrupting_the_global(self, bad):
        """#4600's guarantee, verified through the write-back path (#4601)."""
        settings = {"enabled": True, "preset": "gentle", "intensity": 0.8}

        await _run(settings, {"intensity": bad})

        assert settings["intensity"] == 0.8

    async def test_case_is_normalised_before_storing(self):
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}

        await _run(settings, {"preset": "WARM"})

        assert settings["preset"] == "warm", (
            "the profile map is keyed by lowercased preset, so the stored value "
            "must be lowercased too or the lookup misses"
        )


class TestPreWarmReadsTheSameValues:
    """SIBLING: _preprocess_upcoming_chunks reads the global too."""

    async def test_global_reflects_the_stream_after_play(self):
        settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}

        await _run(settings, {"preset": "bright", "intensity": 0.6})

        # This is exactly what routers/enhancement.py passes to the pre-warm.
        assert (
            settings.get("preset", "adaptive"),
            settings.get("intensity", 1.0),
        ) == ("bright", 0.6)
