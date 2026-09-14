"""
Regression tests for the untracked proactive-buffer task (#5378)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``stream_enhanced_audio`` fires ``buffer_presets_for_track`` through
``spawn_background_task`` on every enhanced stream start (#3884).
``spawn_background_task`` only attaches exception logging — it registers the
task nowhere — so the returned handle used to be dropped on the floor. Nothing
in the three teardown paths that cancel a stream (``_cancel_prior_task`` for
play/seek, ``handle_stop``, ``teardown_connection``) knew the task existed, and
up to three chunks of DSP kept running after the user had stopped, sought or
disconnected, contending for the same shared ``ProcessorFactory`` entry as the
successor stream.

The fix scopes the task to the lifetime of the stream that spawned it rather
than inventing a second per-``ws_id`` registry: ``stream_enhanced_audio`` keeps
the handle and drains it in its own ``finally``, and hands the buffering the
stream's ``chunk_cancel_event`` so a render already inside an executor thread
aborts too (cancelling the coroutine alone cannot stop that — #4815). Because
the streaming task itself is what all three teardown paths already cancel, the
buffering now dies with every one of them.

SIBLING harness: mocked-processor/controller/websocket wiring mirrors
test_proactive_buffer_wiring_3884.py.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import json
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController, ws_id as _ws_id
from core.proactive_buffer import AVAILABLE_PRESETS, buffer_presets_for_track

TRACK_ID = 42
PRESET = "adaptive"
INTENSITY = 0.8
SAMPLE_RATE = 44100
CHUNK_DURATION = 15.0
TOTAL_CHUNKS = 4
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


def _make_processor() -> MagicMock:
    proc = MagicMock()
    proc.track_id = TRACK_ID
    proc.preset = PRESET
    proc.intensity = INTENSITY
    proc.sample_rate = SAMPLE_RATE
    proc.channels = 2
    proc.total_chunks = TOTAL_CHUNKS
    proc.chunk_duration = CHUNK_DURATION
    proc.chunk_interval = CHUNK_DURATION
    proc.duration = CHUNK_DURATION * TOTAL_CHUNKS
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


class _BufferProbe:
    """Stands in for buffer_presets_for_track: records that it started, hangs
    until cancelled (like a real multi-chunk buffering run would), and records
    the cancellation plus the cancel_event it was handed."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False
        self.finished = False
        self.cancel_event: threading.Event | None = None

    async def __call__(self, *args, **kwargs) -> None:
        self.cancel_event = kwargs.get("cancel_event")
        self.started.set()
        try:
            await asyncio.sleep(3600)
            self.finished = True
        except asyncio.CancelledError:
            self.cancelled = True
            raise


async def _run_until_buffering_started(
    controller: AudioStreamController, ws: MagicMock, probe: _BufferProbe
) -> "asyncio.Task[None]":
    task = asyncio.create_task(
        controller.stream_enhanced_audio(
            track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
        )
    )
    await asyncio.wait_for(probe.started.wait(), timeout=5)
    return task


class TestProactiveBufferDiesWithItsStream:
    """The buffering must not outlive the stream that spawned it — which is
    what makes stop/seek/disconnect (all of which cancel that stream task)
    stop it."""

    @pytest.mark.asyncio
    async def test_cancelling_the_stream_task_cancels_the_buffering(self):
        """The stop/seek/disconnect case: every one of the three teardown
        paths cancels the streaming task, so cancelling it here is the shared
        trigger they all reduce to."""
        processor = _make_processor()
        controller, ws = _wire_controller(processor)
        probe = _BufferProbe()

        # The stream must stay alive while the buffering runs, so the only
        # thing that can end the buffering is the teardown under test.
        async def _hang(*args, **kwargs):
            await asyncio.sleep(3600)

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)), \
             patch("core.stream_enhanced.pump_enhanced_chunks", new=_hang), \
             patch("core.stream_enhanced.buffer_presets_for_track", new=probe):
            task = await _run_until_buffering_started(controller, ws, probe)

            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5)
            except asyncio.CancelledError:
                pass

        assert probe.cancelled, (
            "the proactive-buffer task survived the cancellation of its own "
            "streaming task — it is untracked again (#5378)"
        )
        assert not probe.finished

    @pytest.mark.asyncio
    async def test_stream_cancellation_still_releases_the_semaphore(self):
        """The drain added to the `finally` must not shadow the semaphore
        release that the same block owns (streaming-semaphore invariant)."""
        processor = _make_processor()
        controller, ws = _wire_controller(processor)
        probe = _BufferProbe()
        permits_before = controller._stream_semaphore._value

        async def _hang(*args, **kwargs):
            await asyncio.sleep(3600)

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)), \
             patch("core.stream_enhanced.pump_enhanced_chunks", new=_hang), \
             patch("core.stream_enhanced.buffer_presets_for_track", new=probe):
            task = await _run_until_buffering_started(controller, ws, probe)
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5)
            except asyncio.CancelledError:
                pass

        assert controller._stream_semaphore._value == permits_before
        processor.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_buffering_is_drained_when_the_stream_ends_normally(self):
        """Nothing is lost by draining on a clean exit either: by the time the
        chunk loop has run to the end, the stream has rendered those chunks
        itself, so an unfinished warm-up has nothing left to contribute."""
        processor = _make_processor()
        controller, ws = _wire_controller(processor)
        probe = _BufferProbe()

        async def _complete(*args, **kwargs):
            # Let the buffering actually begin first — otherwise the task is
            # cancelled before its coroutine ever runs and the test would pass
            # without exercising anything.
            await asyncio.wait_for(probe.started.wait(), timeout=5)
            result = MagicMock()
            result.stopped_early = False
            result.failed_chunks = []
            result.delivered_samples = SAMPLE_RATE
            return result

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)), \
             patch.object(controller, "_send_stream_completion", new=AsyncMock()), \
             patch("core.stream_enhanced.pump_enhanced_chunks", new=_complete), \
             patch("core.stream_enhanced.buffer_presets_for_track", new=probe):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
            )

        assert probe.cancelled
        assert not probe.finished


class TestProactiveBufferSharesTheStreamsCancelEvent:
    """Cancelling the coroutine cannot stop DSP already running in an executor
    thread (#4815), so the buffering also gets the stream's own cancel event —
    the very object stop/seek/disconnect set() before cancelling the task."""

    @pytest.mark.asyncio
    async def test_buffering_receives_the_streams_registered_cancel_event(self):
        from routers.system import _stream_chunk_cancel_events

        processor = _make_processor()
        controller, ws = _wire_controller(processor)
        probe = _BufferProbe()

        async def _hang(*args, **kwargs):
            await asyncio.sleep(3600)

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)), \
             patch("core.stream_enhanced.pump_enhanced_chunks", new=_hang), \
             patch("core.stream_enhanced.buffer_presets_for_track", new=probe):
            task = await _run_until_buffering_started(controller, ws, probe)
            registered = _stream_chunk_cancel_events.get(_ws_id(ws))

            assert registered is not None
            assert probe.cancel_event is registered, (
                "proactive buffering must share the stream's registered "
                "chunk-cancel event, otherwise a set() from handle_stop / "
                "_cancel_prior_task / teardown_connection never reaches it"
            )

            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5)
            except asyncio.CancelledError:
                pass

        _stream_chunk_cancel_events.pop(_ws_id(ws), None)


class TestBufferPresetsForTrackHonoursTheEvent:
    """buffer_presets_for_track's own half of the contract, exercised directly."""

    @pytest.mark.asyncio
    async def test_already_cancelled_builds_no_processor(self, monkeypatch):
        built: list[dict] = []

        def _ctor(**kwargs):
            built.append(kwargs)
            return MagicMock()

        monkeypatch.setattr("core.chunked_processor.ChunkedAudioProcessor", _ctor)

        cancel_event = threading.Event()
        cancel_event.set()
        await buffer_presets_for_track(
            track_id=1, filepath="/fake.wav", total_chunks=3, cancel_event=cancel_event
        )

        assert built == [], (
            "a stream that was already torn down must not pay for a "
            "ChunkedAudioProcessor construction per preset"
        )

    @pytest.mark.asyncio
    async def test_event_set_mid_run_stops_before_the_next_chunk(self, monkeypatch):
        processed: list[int] = []
        cancel_event = threading.Event()

        def _ctor(**kwargs):
            inst = MagicMock()
            missing = MagicMock()
            missing.exists.return_value = False
            inst._get_chunk_path.return_value = missing

            async def _process(chunk_idx, fast_start=False):
                processed.append(chunk_idx)
                cancel_event.set()  # the user stops/seeks while chunk 0 renders
                return (Path(f"/tmp/chunk_{chunk_idx}.wav"), MagicMock())

            inst.process_chunk_safe = _process
            inst.close = MagicMock()
            return inst

        monkeypatch.setattr("core.chunked_processor.ChunkedAudioProcessor", _ctor)

        await buffer_presets_for_track(
            track_id=1, filepath="/fake.wav", total_chunks=3, cancel_event=cancel_event
        )

        assert processed == [0], (
            f"buffering continued past the cancellation: rendered {processed}"
        )

    @pytest.mark.asyncio
    async def test_processor_is_handed_the_cancel_event(self, monkeypatch):
        built: list[dict] = []
        cancel_event = threading.Event()

        def _ctor(**kwargs):
            built.append(kwargs)
            inst = MagicMock()
            cached = MagicMock()
            cached.exists.return_value = True
            inst._get_chunk_path.return_value = cached
            inst.close = MagicMock()
            return inst

        monkeypatch.setattr("core.chunked_processor.ChunkedAudioProcessor", _ctor)

        await buffer_presets_for_track(
            track_id=1, filepath="/fake.wav", total_chunks=1, cancel_event=cancel_event
        )

        assert len(built) == len(AVAILABLE_PRESETS)
        assert all(kw.get("cancel_event") is cancel_event for kw in built), (
            "in-flight chunk DSP can only abort if the processor holds the "
            "stream's cancel event (#4815)"
        )

    @pytest.mark.asyncio
    async def test_no_event_keeps_the_old_behaviour(self, monkeypatch):
        """cancel_event is optional: callers without a stream (tests, future
        prefetch paths) must keep working with every check a no-op."""
        processed: list[int] = []

        def _ctor(**kwargs):
            inst = MagicMock()
            missing = MagicMock()
            missing.exists.return_value = False
            inst._get_chunk_path.return_value = missing

            async def _process(chunk_idx, fast_start=False):
                processed.append(chunk_idx)
                return (Path(f"/tmp/chunk_{chunk_idx}.wav"), MagicMock())

            inst.process_chunk_safe = _process
            inst.close = MagicMock()
            return inst

        monkeypatch.setattr("core.chunked_processor.ChunkedAudioProcessor", _ctor)

        await buffer_presets_for_track(track_id=1, filepath="/fake.wav", total_chunks=2)

        assert processed == [0, 1] * len(AVAILABLE_PRESETS)
