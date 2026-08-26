"""
Regression tests for the dead proactive-buffer wiring (#3884)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``proactive_buffer.buffer_presets_for_track`` was exported, imported in
main.py, threaded through config/routes.py into
``create_player_router(buffer_presets_fn=...)`` — a REST router that never
triggers streaming and never called the parameter. ~120 lines of
proactive-buffering logic never executed.

The fix calls ``buffer_presets_for_track`` directly from
``stream_enhanced.py``'s ``stream_enhanced_audio`` (the actual play_enhanced
entry point), fire-and-forget via ``spawn_background_task``, right after the
processor's metadata is validated (track_id/filepath/intensity/total_chunks
are all available there). Deliberately NOT hooked into
``stream_enhanced_audio_from_position`` (stream_seek.py, mid-track seeks) —
proactive buffering only ever warms the first 3 chunks (first ~45s), which is
only useful from true track start.

SIBLING harness: mocked-processor/controller/websocket wiring mirrors
test_stream_processor_close_on_teardown_5253.py.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController

TRACK_ID = 42
PRESET = "adaptive"
INTENSITY = 0.8
SAMPLE_RATE = 44100
CHUNK_DURATION = 15.0
TOTAL_CHUNKS = 1
FILEPATH = "/tmp/fake.wav"


def _make_websocket() -> MagicMock:
    ws = MagicMock()
    ws.client_state = MagicMock()
    ws.client_state.name = "CONNECTED"

    async def fake_send_text(text: str) -> None:
        json.loads(text)

    ws.send_text = AsyncMock(side_effect=fake_send_text)
    ws.send_bytes = AsyncMock()
    return ws


def _make_single_chunk_processor() -> MagicMock:
    proc = MagicMock()
    proc.track_id = TRACK_ID
    proc.preset = PRESET
    proc.intensity = INTENSITY
    proc.sample_rate = SAMPLE_RATE
    proc.channels = 2
    proc.total_chunks = TOTAL_CHUNKS
    proc.chunk_duration = CHUNK_DURATION
    proc.chunk_interval = CHUNK_DURATION
    proc.duration = CHUNK_DURATION

    good_audio = np.zeros((SAMPLE_RATE * int(CHUNK_DURATION), 2), dtype=np.float32)

    async def process_chunk_safe(chunk_idx: int, fast_start: bool = False):
        return (Path(f"/tmp/chunk_{chunk_idx}.wav"), good_audio.copy())

    proc.process_chunk_safe = process_chunk_safe
    proc.close = MagicMock()
    return proc


def _wire_controller(processor: MagicMock) -> tuple[AudioStreamController, MagicMock]:
    ws = _make_websocket()
    controller = AudioStreamController(
        chunked_processor_class=MagicMock(return_value=processor),
    )
    controller._send_stream_start = AsyncMock(return_value=True)
    controller.chunked_processor_class = MagicMock(return_value=processor)

    mock_track = MagicMock()
    mock_track.filepath = FILEPATH
    factory = MagicMock()
    factory.tracks.get_by_id.return_value = mock_track
    factory.fingerprints.exists.return_value = False
    controller._get_repository_factory = MagicMock(return_value=factory)
    return controller, ws


class TestProactiveBufferFiresOnPlayStart:
    """#3884: the real play_enhanced entry point must actually invoke
    buffer_presets_for_track, not just accept it as a dead parameter."""

    @pytest.mark.asyncio
    async def test_stream_enhanced_audio_fires_proactive_buffering(self):
        processor = _make_single_chunk_processor()
        controller, ws = _wire_controller(processor)

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)), \
             patch("core.stream_enhanced.buffer_presets_for_track",
                   new=AsyncMock(return_value=None)) as mock_buffer:
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
            )
            # spawn_background_task's asyncio.create_task doesn't run the
            # coroutine body until the event loop gets a turn.
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        mock_buffer.assert_called_once_with(TRACK_ID, FILEPATH, INTENSITY, TOTAL_CHUNKS)

    @pytest.mark.asyncio
    async def test_proactive_buffer_failure_does_not_break_the_stream(self):
        """spawn_background_task logs a failing background task instead of
        propagating it — the stream itself must complete normally even if
        proactive buffering blows up."""
        processor = _make_single_chunk_processor()
        controller, ws = _wire_controller(processor)

        async def _explode(*args, **kwargs):
            raise RuntimeError("proactive buffering exploded")

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)), \
             patch("core.stream_enhanced.buffer_presets_for_track", side_effect=_explode):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        # The stream itself ran to completion regardless of the background
        # task's fate.
        processor.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_enhanced_audio_from_position_does_not_fire_proactive_buffering(self):
        """Seeking mid-track must NOT re-trigger proactive buffering of the
        first 3 chunks -- that's only useful from true track start."""
        processor = _make_single_chunk_processor()
        controller, ws = _wire_controller(processor)

        with patch("core.stream_seek.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)), \
             patch("core.stream_enhanced.buffer_presets_for_track",
                   new=AsyncMock(return_value=None)) as mock_buffer:
            await controller.stream_enhanced_audio_from_position(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY,
                websocket=ws, start_position=30.0,
            )
            await asyncio.sleep(0)

        mock_buffer.assert_not_called()


class TestDeadWiringRemoved:
    """The old, never-invoked wiring chain (main.py -> config/routes.py ->
    create_player_router(buffer_presets_fn=...)) is gone now that the real
    call site exists directly in stream_enhanced.py."""

    def test_create_player_router_no_longer_accepts_buffer_presets_fn(self):
        import inspect

        from routers.player import create_player_router

        assert "buffer_presets_fn" not in inspect.signature(create_player_router).parameters

    def test_stream_enhanced_imports_the_real_buffer_presets_for_track(self):
        from core import stream_enhanced
        from core.proactive_buffer import buffer_presets_for_track

        assert stream_enhanced.buffer_presets_for_track is buffer_presets_for_track
