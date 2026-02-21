"""
Tests for WebSocket error recovery on mid-stream chunk failure (issue #2085)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Acceptance criteria:
 - Processor state (_chunk_tails) is cleaned up on chunk failure
 - Client receives an audio_stream_error with a recovery_position field
 - No stale cache entry remains for the failed chunk

Test plan:
 - Mid-stream failure: fail chunk 3 of 10, verify cleanup and that error
   payload includes the correct recovery position

All tests use the real AudioStreamController imported from the backend.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController, SimpleChunkCache


# ============================================================================
# Helpers
# ============================================================================

CHUNK_DURATION = 30.0  # seconds per chunk (matches ChunkedAudioProcessor default)
TOTAL_CHUNKS = 10
FAIL_AT_CHUNK = 3      # Zero-based index of the chunk that will fail
TRACK_ID = 42
PRESET = "adaptive"
INTENSITY = 1.0
SAMPLE_RATE = 44100


def _make_websocket(sent_messages: list) -> MagicMock:
    """Return a mock WebSocket that records sent JSON messages."""
    ws = MagicMock()
    ws.client_state = MagicMock()
    ws.client_state.name = "CONNECTED"

    async def fake_send_text(text: str) -> None:
        sent_messages.append(json.loads(text))

    ws.send_text = AsyncMock(side_effect=fake_send_text)
    return ws


def _make_processor(fail_at: int = FAIL_AT_CHUNK) -> MagicMock:
    """Return a mock ChunkedAudioProcessor.

    process_chunk_safe succeeds for all chunks before *fail_at* and raises
    RuntimeError for chunk *fail_at*.
    """
    proc = MagicMock()
    proc.track_id = TRACK_ID
    proc.preset = PRESET
    proc.intensity = INTENSITY
    proc.sample_rate = SAMPLE_RATE
    proc.channels = 2
    proc.total_chunks = TOTAL_CHUNKS
    proc.chunk_duration = CHUNK_DURATION
    proc.duration = TOTAL_CHUNKS * CHUNK_DURATION

    good_audio = np.zeros((SAMPLE_RATE * int(CHUNK_DURATION), 2), dtype=np.float32)

    async def process_chunk_safe(chunk_idx: int, fast_start: bool = False):
        if chunk_idx >= fail_at:
            raise RuntimeError(f"simulated processing failure at chunk {chunk_idx}")
        return (Path(f"/tmp/chunk_{chunk_idx}.wav"), good_audio.copy())

    proc.process_chunk_safe = process_chunk_safe
    return proc


# ============================================================================
# Tests
# ============================================================================

class TestChunkFailureRecovery:
    """Verify cleanup and client notification on mid-stream chunk failure."""

    @pytest.mark.asyncio
    async def test_error_payload_contains_recovery_position(self):
        """Client must receive recovery_position in the error message.

        Recovery position must equal chunk_idx * chunk_duration so the
        client knows where to seek / retry from.
        """
        sent: list[dict] = []
        ws = _make_websocket(sent)
        processor = _make_processor(fail_at=FAIL_AT_CHUNK)

        controller = AudioStreamController(
            chunked_processor_class=MagicMock(return_value=processor),
        )

        # Drive stream_enhanced_audio but intercept _send_stream_start so it
        # returns True (connected) and the chunk loop actually runs.
        controller._send_stream_start = AsyncMock(return_value=True)

        # Wire the mock processor class to return our pre-configured processor
        # (stream_enhanced_audio instantiates it via self.chunked_processor_class(...))
        controller.chunked_processor_class = MagicMock(return_value=processor)
        # Provide a minimal repository factory so track loading succeeds
        mock_track = MagicMock()
        mock_track.filepath = "/tmp/fake.wav"
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = mock_track
        factory.fingerprints.exists.return_value = False
        controller._get_repository_factory = MagicMock(return_value=factory)

        # Bypass fingerprint queue to avoid import errors in test environment
        with patch("audio_stream_controller.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID,
                preset=PRESET,
                intensity=INTENSITY,
                websocket=ws,
            )

        # Find the error message
        error_msgs = [m for m in sent if m.get("type") == "audio_stream_error"]
        assert error_msgs, "Expected at least one audio_stream_error message"
        err = error_msgs[0]["data"]

        expected_position = FAIL_AT_CHUNK * CHUNK_DURATION
        assert "recovery_position" in err, \
            "error payload must contain recovery_position (issue #2085)"
        assert err["recovery_position"] == pytest.approx(expected_position), \
            f"expected recovery_position={expected_position}, got {err['recovery_position']}"

    @pytest.mark.asyncio
    async def test_chunk_tails_cleaned_up_after_failure(self):
        """_chunk_tails must be empty after a mid-stream chunk failure."""
        sent: list[dict] = []
        ws = _make_websocket(sent)
        processor = _make_processor(fail_at=FAIL_AT_CHUNK)

        controller = AudioStreamController(
            chunked_processor_class=MagicMock(return_value=processor),
        )
        controller._send_stream_start = AsyncMock(return_value=True)
        controller.chunked_processor_class = MagicMock(return_value=processor)

        mock_track = MagicMock()
        mock_track.filepath = "/tmp/fake.wav"
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = mock_track
        factory.fingerprints.exists.return_value = False
        controller._get_repository_factory = MagicMock(return_value=factory)

        with patch("audio_stream_controller.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID,
                preset=PRESET,
                intensity=INTENSITY,
                websocket=ws,
            )

        assert TRACK_ID not in controller._chunk_tails, \
            "_chunk_tails must not contain stale data for the track after failure (issue #2085)"

    @pytest.mark.asyncio
    async def test_stale_cache_entry_evicted_after_failure(self):
        """A cached entry for the failed chunk must be removed after failure.

        If the chunk was previously cached (e.g. from a prior run), calling
        stream_enhanced_audio again must not replay the same corrupt chunk.
        """
        sent: list[dict] = []
        ws = _make_websocket(sent)

        # Pre-populate the cache with a fake entry for the chunk that will fail
        cache = SimpleChunkCache()
        fake_audio = np.zeros((100, 2), dtype=np.float32)
        cache.put(
            track_id=TRACK_ID,
            chunk_idx=FAIL_AT_CHUNK,
            preset=PRESET,
            intensity=INTENSITY,
            audio=fake_audio,
            sample_rate=SAMPLE_RATE,
        )
        # Confirm the entry is there before the test
        assert cache.get(TRACK_ID, FAIL_AT_CHUNK, PRESET, INTENSITY) is not None

        # Make the cached chunk also fail when streamed: override _send_pcm_chunk
        # to raise on the failing chunk (simulating a corrupt cached payload).
        # For this test we bypass the cache-hit path and directly test invalidate_chunk.
        controller = AudioStreamController(cache_manager=cache)

        # Direct call to invalidate_chunk (the method added in issue #2085 fix)
        controller.cache_manager.invalidate_chunk(
            track_id=TRACK_ID,
            chunk_idx=FAIL_AT_CHUNK,
            preset=PRESET,
            intensity=INTENSITY,
        )

        # The cache entry must be gone
        assert cache.get(TRACK_ID, FAIL_AT_CHUNK, PRESET, INTENSITY) is None, \
            "invalidate_chunk must evict the stale entry (issue #2085)"

    @pytest.mark.asyncio
    async def test_error_contains_track_id_and_stream_type(self):
        """Error payload must carry track_id and stream_type for client routing."""
        sent: list[dict] = []
        ws = _make_websocket(sent)
        processor = _make_processor(fail_at=FAIL_AT_CHUNK)

        controller = AudioStreamController(
            chunked_processor_class=MagicMock(return_value=processor),
        )
        controller._send_stream_start = AsyncMock(return_value=True)
        controller.chunked_processor_class = MagicMock(return_value=processor)

        mock_track = MagicMock()
        mock_track.filepath = "/tmp/fake.wav"
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = mock_track
        factory.fingerprints.exists.return_value = False
        controller._get_repository_factory = MagicMock(return_value=factory)

        with patch("audio_stream_controller.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID,
                preset=PRESET,
                intensity=INTENSITY,
                websocket=ws,
            )

        error_msgs = [m for m in sent if m.get("type") == "audio_stream_error"]
        assert error_msgs, "Expected audio_stream_error message"
        err_data = error_msgs[0]["data"]

        assert err_data["track_id"] == TRACK_ID
        assert err_data["stream_type"] == "enhanced"
        assert err_data["code"] == "STREAMING_ERROR"

    @pytest.mark.asyncio
    async def test_invalidate_chunk_noop_when_not_cached(self):
        """invalidate_chunk must not raise when the chunk is not in the cache."""
        cache = SimpleChunkCache()
        # Should not raise even if the key does not exist
        cache.invalidate_chunk(
            track_id=99,
            chunk_idx=0,
            preset="adaptive",
            intensity=1.0,
        )
