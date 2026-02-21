"""
Tests for AudioStreamController Streaming Lifecycle
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

End-to-end tests for stream_enhanced_audio and stream_normal_audio,
verifying the complete message lifecycle: start → chunks → end,
and error/disconnect handling with mocked WebSocket.

Closes issue #2307.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

# Add backend to path (belt-and-suspenders alongside conftest)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from core.audio_stream_controller import AudioStreamController, MAX_CONCURRENT_STREAMS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TRACK_ID = 42
FILEPATH = "/tmp/fake_test_track.mp3"
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_DURATION = 15.0
TOTAL_CHUNKS = 3
DURATION = CHUNK_DURATION * TOTAL_CHUNKS
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)
TOTAL_FRAMES = CHUNK_SAMPLES * TOTAL_CHUNKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ws(connected: bool = True) -> AsyncMock:
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.client_state = Mock()
    ws.client_state.name = "CONNECTED" if connected else "DISCONNECTED"
    ws.send_text = AsyncMock()
    return ws


def _make_processor(
    track_id: int = TRACK_ID,
    total_chunks: int = TOTAL_CHUNKS,
) -> Mock:
    """Create a mock ChunkedAudioProcessor with silence for each chunk."""
    proc = Mock()
    proc.track_id = track_id
    proc.total_chunks = total_chunks
    proc.sample_rate = SAMPLE_RATE
    proc.channels = CHANNELS
    proc.duration = DURATION
    proc.chunk_duration = CHUNK_DURATION
    proc.chunk_interval = CHUNK_DURATION
    proc.preset = "balanced"
    proc.intensity = 0.7
    silence = np.zeros((CHUNK_SAMPLES, CHANNELS), dtype=np.float32)
    proc.process_chunk_safe = AsyncMock(return_value=("/tmp/chunk.wav", silence))
    return proc


def _make_factory(filepath: str = FILEPATH, track_found: bool = True) -> Mock:
    """
    Create a mock RepositoryFactory.

    spec=['tracks', 'fingerprints'] prevents hasattr(factory, 'session_factory')
    from returning True, which would trigger FingerprintGenerator initialization.
    """
    factory = Mock(spec=["tracks", "fingerprints"])
    if track_found:
        track = Mock()
        track.id = TRACK_ID
        track.filepath = filepath
        factory.tracks.get_by_id = Mock(return_value=track)
    else:
        factory.tracks.get_by_id = Mock(return_value=None)
    factory.fingerprints.exists = Mock(return_value=False)
    return factory


def _make_controller(
    proc: Mock | None = None,
    factory: Mock | None = None,
) -> AudioStreamController:
    """
    Create an AudioStreamController with mocked processor class and factory.

    proc_class is a synchronous callable; asyncio.to_thread(proc_class, **kwargs)
    runs it in the thread pool and returns the mock processor — no need to patch
    asyncio.to_thread.
    """
    if proc is None:
        proc = _make_processor()
    if factory is None:
        factory = _make_factory()

    def proc_class(**kwargs) -> Mock:
        return proc

    return AudioStreamController(
        chunked_processor_class=proc_class,
        get_repository_factory=lambda: factory,
    )


def _get_sent_messages(ws: AsyncMock) -> list[dict]:
    """Parse all JSON messages sent via ws.send_text."""
    return [json.loads(call.args[0]) for call in ws.send_text.call_args_list]


def _get_message_types(ws: AsyncMock) -> list[str]:
    """Return ordered list of message types sent via ws.send_text."""
    return [msg["type"] for msg in _get_sent_messages(ws)]


def _make_sf_class(total_chunks: int = TOTAL_CHUNKS) -> MagicMock:
    """
    Build a soundfile.SoundFile class mock.

    First call (metadata read in _get_audio_info): returns samplerate, channels, len.
    Subsequent calls (chunk reads in _read_audio_chunk): return seek/read context.
    """
    total_frames = CHUNK_SAMPLES * total_chunks
    chunk_audio = np.zeros((CHUNK_SAMPLES, CHANNELS), dtype=np.float32)

    # Metadata context manager
    meta_ctx = MagicMock()
    meta_ctx.__enter__.return_value = meta_ctx
    meta_ctx.__exit__.return_value = False
    meta_ctx.samplerate = SAMPLE_RATE
    meta_ctx.channels = CHANNELS
    meta_ctx.__len__.return_value = total_frames

    # Per-chunk context manager factory
    def make_chunk_ctx() -> MagicMock:
        ctx = MagicMock()
        ctx.__enter__.return_value = ctx
        ctx.__exit__.return_value = False
        ctx.read.return_value = chunk_audio.copy()
        return ctx

    chunk_ctxs = [make_chunk_ctx() for _ in range(total_chunks)]
    return MagicMock(side_effect=[meta_ctx] + chunk_ctxs)


# ---------------------------------------------------------------------------
# stream_enhanced_audio tests
# ---------------------------------------------------------------------------

class TestStreamEnhancedAudioLifecycle:
    """End-to-end lifecycle tests for stream_enhanced_audio."""

    @pytest.mark.asyncio
    async def test_happy_path_message_order(self):
        """Messages arrive in order: start → chunks → end, with no errors.

        Note: fingerprint_progress may precede audio_stream_start due to the
        non-blocking fingerprint check in Phase 7.5 of the streaming pipeline.
        """
        proc = _make_processor()
        ws = _make_ws()
        with patch.object(Path, "exists", return_value=True):
            ctrl = _make_controller(proc=proc)
            await ctrl.stream_enhanced_audio(
                track_id=TRACK_ID, preset="balanced", intensity=0.7, websocket=ws
            )

        types = _get_message_types(ws)
        assert "audio_stream_start" in types
        assert "audio_chunk" in types
        assert "audio_stream_end" in types
        assert "audio_stream_error" not in types

        # Ordering: start → all chunks → end
        start_idx = types.index("audio_stream_start")
        end_idx = types.index("audio_stream_end")
        chunk_indices = [i for i, t in enumerate(types) if t == "audio_chunk"]
        assert all(start_idx < i for i in chunk_indices)
        assert start_idx < end_idx

    @pytest.mark.asyncio
    async def test_stream_start_metadata(self):
        """audio_stream_start carries correct track metadata."""
        proc = _make_processor()
        ws = _make_ws()
        with patch.object(Path, "exists", return_value=True):
            ctrl = _make_controller(proc=proc)
            await ctrl.stream_enhanced_audio(
                track_id=TRACK_ID, preset="warm", intensity=0.5, websocket=ws
            )

        messages = _get_sent_messages(ws)
        start = next(m for m in messages if m["type"] == "audio_stream_start")
        d = start["data"]
        assert d["track_id"] == TRACK_ID
        assert d["preset"] == "warm"
        assert d["intensity"] == 0.5
        assert d["sample_rate"] == SAMPLE_RATE
        assert d["channels"] == CHANNELS
        assert d["total_chunks"] == TOTAL_CHUNKS
        assert d["total_duration"] == pytest.approx(DURATION)
        assert d["stream_type"] == "enhanced"

    @pytest.mark.asyncio
    async def test_all_chunks_processed(self):
        """process_chunk_safe is called once for each chunk."""
        proc = _make_processor()
        ws = _make_ws()
        with patch.object(Path, "exists", return_value=True):
            ctrl = _make_controller(proc=proc)
            await ctrl.stream_enhanced_audio(
                track_id=TRACK_ID, preset="balanced", intensity=0.7, websocket=ws
            )

        assert proc.process_chunk_safe.call_count == TOTAL_CHUNKS

    @pytest.mark.asyncio
    async def test_stream_end_metadata(self):
        """audio_stream_end carries correct total_samples and duration."""
        proc = _make_processor()
        ws = _make_ws()
        with patch.object(Path, "exists", return_value=True):
            ctrl = _make_controller(proc=proc)
            await ctrl.stream_enhanced_audio(
                track_id=TRACK_ID, preset="balanced", intensity=0.7, websocket=ws
            )

        messages = _get_sent_messages(ws)
        end = next(m for m in messages if m["type"] == "audio_stream_end")
        d = end["data"]
        assert d["track_id"] == TRACK_ID
        assert d["total_samples"] == int(DURATION * SAMPLE_RATE)
        assert d["duration"] == pytest.approx(DURATION)

    @pytest.mark.asyncio
    async def test_cleanup_on_success(self):
        """On success: active_streams entry removed, semaphore returned."""
        proc = _make_processor()
        ws = _make_ws()
        with patch.object(Path, "exists", return_value=True):
            ctrl = _make_controller(proc=proc)
            initial_value = ctrl._stream_semaphore._value
            await ctrl.stream_enhanced_audio(
                track_id=TRACK_ID, preset="balanced", intensity=0.7, websocket=ws
            )

        assert TRACK_ID not in ctrl.active_streams
        assert ctrl._stream_semaphore._value == initial_value

    @pytest.mark.asyncio
    async def test_track_not_found_sends_error(self):
        """When track is absent from library, audio_stream_error is sent."""
        factory = _make_factory(track_found=False)
        ws = _make_ws()
        ctrl = _make_controller(factory=factory)
        await ctrl.stream_enhanced_audio(
            track_id=TRACK_ID, preset="balanced", intensity=0.7, websocket=ws
        )

        types = _get_message_types(ws)
        assert "audio_stream_error" in types
        assert "audio_stream_start" not in types
        messages = _get_sent_messages(ws)
        err = next(m for m in messages if m["type"] == "audio_stream_error")
        assert "not found" in err["data"]["error"].lower()

    @pytest.mark.asyncio
    async def test_file_not_found_sends_error(self):
        """When audio file is missing on disk, audio_stream_error is sent."""
        ws = _make_ws()
        with patch.object(Path, "exists", return_value=False):
            ctrl = _make_controller()
            await ctrl.stream_enhanced_audio(
                track_id=TRACK_ID, preset="balanced", intensity=0.7, websocket=ws
            )

        types = _get_message_types(ws)
        assert "audio_stream_error" in types
        assert "audio_stream_start" not in types

    @pytest.mark.asyncio
    async def test_chunk_failure_sends_error_with_recovery_position(self):
        """When chunk 1 fails, audio_stream_error includes recovery_position."""
        proc = _make_processor()
        silence = np.zeros((CHUNK_SAMPLES, CHANNELS), dtype=np.float32)
        proc.process_chunk_safe = AsyncMock(
            side_effect=[("/tmp/c0.wav", silence), RuntimeError("DSP exploded")]
        )
        ws = _make_ws()
        with patch.object(Path, "exists", return_value=True):
            ctrl = _make_controller(proc=proc)
            await ctrl.stream_enhanced_audio(
                track_id=TRACK_ID, preset="balanced", intensity=0.7, websocket=ws
            )

        messages = _get_sent_messages(ws)
        types = [m["type"] for m in messages]
        assert "audio_stream_start" in types
        assert "audio_stream_error" in types
        assert "audio_stream_end" not in types
        err = next(m for m in messages if m["type"] == "audio_stream_error")
        # Chunk index 1 failed → recovery_position = 1 × CHUNK_DURATION
        assert "recovery_position" in err["data"]
        assert err["data"]["recovery_position"] == pytest.approx(CHUNK_DURATION)

    @pytest.mark.asyncio
    async def test_chunk_failure_cleans_up(self):
        """After a chunk failure, active_streams is cleared and semaphore returned."""
        proc = _make_processor()
        proc.process_chunk_safe = AsyncMock(side_effect=RuntimeError("always fails"))
        ws = _make_ws()
        with patch.object(Path, "exists", return_value=True):
            ctrl = _make_controller(proc=proc)
            semaphore_before = ctrl._stream_semaphore._value
            await ctrl.stream_enhanced_audio(
                track_id=TRACK_ID, preset="balanced", intensity=0.7, websocket=ws
            )

        assert TRACK_ID not in ctrl.active_streams
        assert ctrl._stream_semaphore._value == semaphore_before

    @pytest.mark.asyncio
    async def test_semaphore_exhausted_sends_error(self):
        """When stream limit is reached, audio_stream_error 'busy' is sent immediately."""
        ws = _make_ws()
        ctrl = _make_controller()
        with patch(
            "audio_stream_controller.asyncio.wait_for",
            side_effect=asyncio.TimeoutError(),
        ):
            await ctrl.stream_enhanced_audio(
                track_id=TRACK_ID, preset="balanced", intensity=0.7, websocket=ws
            )

        types = _get_message_types(ws)
        assert "audio_stream_error" in types
        messages = _get_sent_messages(ws)
        err = next(m for m in messages if m["type"] == "audio_stream_error")
        error_text = err["data"]["error"].lower()
        assert "busy" in error_text or "stream" in error_text

    @pytest.mark.asyncio
    async def test_disconnect_mid_stream_stops_processing(self):
        """When client disconnects after chunk 0, subsequent chunks are not processed."""
        total_chunks = 5
        proc = _make_processor(total_chunks=total_chunks)
        silence = np.zeros((CHUNK_SAMPLES, CHANNELS), dtype=np.float32)

        chunks_processed = [0]

        async def counting_process(chunk_idx, **kwargs):
            chunks_processed[0] += 1
            return "/tmp/c.wav", silence

        proc.process_chunk_safe = AsyncMock(side_effect=counting_process)
        ws = _make_ws()

        with patch.object(Path, "exists", return_value=True):
            ctrl = _make_controller(proc=proc)

            # Disconnect once first chunk's frames are all sent
            original_is_connected = ctrl._is_websocket_connected

            def disconnect_after_chunk_zero(websocket):
                if chunks_processed[0] >= 1:
                    return False
                return original_is_connected(websocket)

            ctrl._is_websocket_connected = disconnect_after_chunk_zero

            await ctrl.stream_enhanced_audio(
                track_id=TRACK_ID, preset="balanced", intensity=0.7, websocket=ws
            )

        # Only the first chunk (index 0) should have been processed before disconnect
        assert chunks_processed[0] < total_chunks


# ---------------------------------------------------------------------------
# stream_normal_audio tests
# ---------------------------------------------------------------------------

class TestStreamNormalAudioLifecycle:
    """End-to-end lifecycle tests for stream_normal_audio."""

    @pytest.mark.asyncio
    async def test_happy_path_message_order(self):
        """Messages arrive in order: start → chunks → end, with no errors."""
        ws = _make_ws()
        factory = _make_factory()
        sf_class = _make_sf_class()
        with (
            patch("soundfile.SoundFile", sf_class),
            patch.object(Path, "exists", return_value=True),
        ):
            ctrl = AudioStreamController(get_repository_factory=lambda: factory)
            await ctrl.stream_normal_audio(track_id=TRACK_ID, websocket=ws)

        types = _get_message_types(ws)
        assert types[0] == "audio_stream_start"
        assert types[-1] == "audio_stream_end"
        assert "audio_chunk" in types
        assert "audio_stream_error" not in types

    @pytest.mark.asyncio
    async def test_stream_start_has_preset_none(self):
        """audio_stream_start for normal audio uses preset='none' and intensity=1.0."""
        ws = _make_ws()
        factory = _make_factory()
        sf_class = _make_sf_class()
        with (
            patch("soundfile.SoundFile", sf_class),
            patch.object(Path, "exists", return_value=True),
        ):
            ctrl = AudioStreamController(get_repository_factory=lambda: factory)
            await ctrl.stream_normal_audio(track_id=TRACK_ID, websocket=ws)

        messages = _get_sent_messages(ws)
        start = next(m for m in messages if m["type"] == "audio_stream_start")
        d = start["data"]
        assert d["preset"] == "none"
        assert d["intensity"] == 1.0
        assert d["track_id"] == TRACK_ID
        assert d["sample_rate"] == SAMPLE_RATE
        assert d["channels"] == CHANNELS
        assert d["total_chunks"] == TOTAL_CHUNKS
        assert d["stream_type"] == "normal"

    @pytest.mark.asyncio
    async def test_cleanup_on_success(self):
        """On success: active_streams entry removed, semaphore returned."""
        ws = _make_ws()
        factory = _make_factory()
        sf_class = _make_sf_class()
        with (
            patch("soundfile.SoundFile", sf_class),
            patch.object(Path, "exists", return_value=True),
        ):
            ctrl = AudioStreamController(get_repository_factory=lambda: factory)
            initial_value = ctrl._stream_semaphore._value
            await ctrl.stream_normal_audio(track_id=TRACK_ID, websocket=ws)

        assert TRACK_ID not in ctrl.active_streams
        assert ctrl._stream_semaphore._value == initial_value

    @pytest.mark.asyncio
    async def test_track_not_found_sends_error(self):
        """When track is absent from library, audio_stream_error is sent."""
        factory = _make_factory(track_found=False)
        ws = _make_ws()
        ctrl = AudioStreamController(get_repository_factory=lambda: factory)
        await ctrl.stream_normal_audio(track_id=TRACK_ID, websocket=ws)

        types = _get_message_types(ws)
        assert "audio_stream_error" in types
        assert "audio_stream_start" not in types

    @pytest.mark.asyncio
    async def test_file_not_found_sends_error(self):
        """When audio file is missing on disk, audio_stream_error is sent."""
        ws = _make_ws()
        factory = _make_factory()
        with patch.object(Path, "exists", return_value=False):
            ctrl = AudioStreamController(get_repository_factory=lambda: factory)
            await ctrl.stream_normal_audio(track_id=TRACK_ID, websocket=ws)

        types = _get_message_types(ws)
        assert "audio_stream_error" in types
        assert "audio_stream_start" not in types

    @pytest.mark.asyncio
    async def test_disconnect_mid_stream_stops_reading(self):
        """When client disconnects mid-stream, no further chunks are read."""
        total_chunks = 5
        ws = _make_ws()
        factory = _make_factory()
        sf_class = _make_sf_class(total_chunks=total_chunks)

        # Flip WebSocket state to DISCONNECTED once enough frames are sent
        send_count = [0]

        async def disconnect_after_some_frames(text):
            msg = json.loads(text)
            if msg["type"] == "audio_chunk":
                send_count[0] += 1
                # Disconnect after first chunk's frames are all delivered
                if send_count[0] >= 5:
                    ws.client_state.name = "DISCONNECTED"

        ws.send_text = AsyncMock(side_effect=disconnect_after_some_frames)

        with (
            patch("soundfile.SoundFile", sf_class),
            patch.object(Path, "exists", return_value=True),
        ):
            ctrl = AudioStreamController(get_repository_factory=lambda: factory)
            await ctrl.stream_normal_audio(track_id=TRACK_ID, websocket=ws)

        # sf_class was called for metadata (1) + chunk reads; fewer than all 5 reads
        # metadata call + fewer than total_chunks chunk reads
        assert sf_class.call_count < 1 + total_chunks

    @pytest.mark.asyncio
    async def test_chunk_read_failure_sends_error_with_recovery_position(self):
        """When chunk 1 read fails, audio_stream_error includes recovery_position."""
        ws = _make_ws()
        factory = _make_factory()
        total_frames = CHUNK_SAMPLES * TOTAL_CHUNKS
        chunk_audio = np.zeros((CHUNK_SAMPLES, CHANNELS), dtype=np.float32)

        # Metadata context
        meta_ctx = MagicMock()
        meta_ctx.__enter__.return_value = meta_ctx
        meta_ctx.__exit__.return_value = False
        meta_ctx.samplerate = SAMPLE_RATE
        meta_ctx.channels = CHANNELS
        meta_ctx.__len__.return_value = total_frames

        # Chunk 0: read succeeds
        good_ctx = MagicMock()
        good_ctx.__enter__.return_value = good_ctx
        good_ctx.__exit__.return_value = False
        good_ctx.read.return_value = chunk_audio.copy()

        # Chunk 1: read raises an I/O error
        bad_ctx = MagicMock()
        bad_ctx.__enter__.return_value = bad_ctx
        bad_ctx.__exit__.return_value = False
        bad_ctx.read.side_effect = RuntimeError("Disk I/O error")

        sf_class = MagicMock(side_effect=[meta_ctx, good_ctx, bad_ctx])

        with (
            patch("soundfile.SoundFile", sf_class),
            patch.object(Path, "exists", return_value=True),
        ):
            ctrl = AudioStreamController(get_repository_factory=lambda: factory)
            await ctrl.stream_normal_audio(track_id=TRACK_ID, websocket=ws)

        messages = _get_sent_messages(ws)
        types = [m["type"] for m in messages]
        assert "audio_stream_start" in types
        assert "audio_stream_error" in types
        assert "audio_stream_end" not in types
        err = next(m for m in messages if m["type"] == "audio_stream_error")
        # Chunk 1 failed → recovery_position = 1 × chunk_duration = 15.0 s
        assert "recovery_position" in err["data"]
        assert err["data"]["recovery_position"] == pytest.approx(15.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
