"""
Tests for WebSocket error recovery on mid-stream chunk failure (issue #2085)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Acceptance criteria:
 - Cached entries for the failed chunk are evicted
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
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController, SimpleChunkCache


# ============================================================================
# Helpers
# ============================================================================

CHUNK_DURATION = 30.0  # seconds per chunk (mock value; loop only uses total_chunks)
CHUNK_INTERVAL = 10.0  # interval between chunk starts
OVERLAP_DURATION = 5.0  # skipped from the head of every chunk >= 1 (#4557)
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
    # send_bytes carries the PCM payload (stream_protocol.safe_send_bytes).
    # Without an AsyncMock here, MagicMock's auto-attribute returns a plain
    # MagicMock that can't be awaited, so every _stream_processed_chunk call
    # fails at delivery (not processing) — masking the exact
    # process-vs-deliver distinction these tests need (#4790).
    ws.send_bytes = AsyncMock()
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
    proc.chunk_interval = CHUNK_INTERVAL  # used by recovery_position computation
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

        #4557 corrected the value. Recovery position is where the client should
        resume, which is the failed chunk's EMITTED start — not its core start
        (chunk_idx * CHUNK_INTERVAL). ChunkOperations.extract_chunk_segment
        skips OVERLAP_DURATION from the head of every chunk >= 1, so by the time
        chunk N fails the client has already heard up to
        N * CHUNK_INTERVAL + OVERLAP_DURATION; resuming at the core start would
        replay OVERLAP_DURATION of already-delivered audio.

        Note the old value was not *observably* broken: the seek path consumed
        it with the same core-timeline error, so the two bugs cancelled. Both
        now sit on the emitted timeline, so the round trip still lands in the
        right place AND the reported number is truthful.
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
        with patch("core.stream_enhanced.Path.exists", return_value=True), \
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

        # Emitted start of the failed chunk (#4557).
        expected_position = FAIL_AT_CHUNK * CHUNK_INTERVAL + OVERLAP_DURATION
        assert "recovery_position" in err, \
            "error payload must contain recovery_position (issue #2085)"
        assert err["recovery_position"] == pytest.approx(expected_position), \
            f"expected recovery_position={expected_position}, got {err['recovery_position']}"

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

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
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


# ============================================================================
# #4790: the terminal audio_stream_end after the #3190 continue-and-keep-going
# recovery path must not claim reason="completed" over a stream with gaps.
# ============================================================================

class TestChunkFailureDoesNotReportCompleted:
    """The chunk-failure `except Exception: ... continue` path (#3190) lets the
    loop reach its natural end having skipped one or more chunks. #4659 only
    guarded the break-driven early exits (stopped_early) — this covers the
    continue-driven one, which #4659 did not reach.
    """

    async def _run_stream(self, fail_at: int):
        sent: list[dict] = []
        ws = _make_websocket(sent)
        processor = _make_processor(fail_at=fail_at)

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

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID,
                preset=PRESET,
                intensity=INTENSITY,
                websocket=ws,
            )
        return sent

    @pytest.mark.asyncio
    async def test_some_chunks_failing_reports_errored_not_completed(self):
        """Chunks 3-9 fail (7 of 10); the loop still runs to its natural end
        (no break), so this is the continue-only path, not stopped_early."""
        sent = await self._run_stream(fail_at=FAIL_AT_CHUNK)

        end_msgs = [m for m in sent if m.get("type") == "audio_stream_end"]
        assert end_msgs, "Expected an audio_stream_end message"
        end_data = end_msgs[0]["data"]

        assert end_data["reason"] != "completed", (
            "a stream with skipped chunks must not report reason='completed' (#4790)"
        )
        assert end_data["reason"] == "errored"

        # Only chunks 0, 1, 2 succeeded.
        expected_samples = FAIL_AT_CHUNK * SAMPLE_RATE * int(CHUNK_DURATION)
        assert end_data["total_samples"] == expected_samples, (
            "total_samples must reflect only the delivered chunks, not the "
            "full track (#4790)"
        )
        assert end_data["total_samples"] < int(
            (TOTAL_CHUNKS * CHUNK_DURATION) * SAMPLE_RATE
        ), "must be less than the full track's sample count"

    @pytest.mark.asyncio
    async def test_every_chunk_failing_delivers_zero_samples(self):
        """If every chunk fails, the client must not see a completed-shaped
        end with the full track duration despite receiving no audio at all —
        the worst case named in the issue's acceptance criteria."""
        sent = await self._run_stream(fail_at=0)

        end_msgs = [m for m in sent if m.get("type") == "audio_stream_end"]
        assert end_msgs, "Expected an audio_stream_end message"
        end_data = end_msgs[0]["data"]

        assert end_data["reason"] != "completed"
        assert end_data["reason"] == "errored"
        assert end_data["total_samples"] == 0
        assert end_data["duration"] == 0

    @pytest.mark.asyncio
    async def test_no_chunk_failures_still_reports_completed(self):
        """Regression guard: a fully successful stream must be unaffected —
        still reports reason='completed' with the full track."""
        sent = await self._run_stream(fail_at=TOTAL_CHUNKS)  # never fails

        end_msgs = [m for m in sent if m.get("type") == "audio_stream_end"]
        assert end_msgs, "Expected an audio_stream_end message"
        end_data = end_msgs[0]["data"]

        assert end_data["reason"] == "completed"
        assert end_data["total_samples"] == int(
            (TOTAL_CHUNKS * CHUNK_DURATION) * SAMPLE_RATE
        )


class TestSeekChunkFailureDoesNotReportCompleted:
    """SIBLING of TestChunkFailureDoesNotReportCompleted for the seek entry
    point (stream_enhanced_audio_from_position) — identical continue-path
    shape, same #4790 bug."""

    @pytest.mark.asyncio
    async def test_some_chunks_failing_reports_errored_not_completed(self):
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

        with patch("core.stream_seek.Path.exists", return_value=True):
            await controller.stream_enhanced_audio_from_position(
                track_id=TRACK_ID,
                preset=PRESET,
                intensity=INTENSITY,
                websocket=ws,
                start_position=0.0,
            )

        end_msgs = [m for m in sent if m.get("type") == "audio_stream_end"]
        assert end_msgs, "Expected an audio_stream_end message"
        end_data = end_msgs[0]["data"]

        assert end_data["reason"] != "completed"
        assert end_data["reason"] == "errored"
        expected_samples = FAIL_AT_CHUNK * SAMPLE_RATE * int(CHUNK_DURATION)
        assert end_data["total_samples"] == expected_samples


class TestNormalChunkFailureDoesNotReportCompleted:
    """SIBLING of TestChunkFailureDoesNotReportCompleted for the normal
    (unprocessed) entry point (stream_normal_audio) — identical continue-path
    shape, same #4790 bug. Reads chunks straight off disk rather than via a
    ChunkedAudioProcessor, so chunk-read failures are injected by patching
    core.stream_normal.sf.SoundFile to fail from the second open onward
    (chunk 0 succeeds, every chunk after it fails)."""

    @pytest.mark.asyncio
    async def test_chunks_after_the_first_failing_reports_errored_not_completed(
        self, tmp_path
    ):
        wav_path = tmp_path / "track.wav"
        sample_rate = 10
        # 3 chunks' worth of frames at CHUNK_INTERVAL=10s / sample_rate=10Hz.
        sf.write(wav_path, np.zeros((300, 2), dtype=np.float32), samplerate=sample_rate)

        sent: list[dict] = []
        ws = _make_websocket(sent)

        controller = AudioStreamController()
        track = MagicMock(filepath=str(wav_path))
        factory = MagicMock()
        factory.tracks.get_by_id.return_value = track
        controller._get_repository_factory = MagicMock(return_value=factory)
        controller._send_stream_start = AsyncMock(return_value=True)

        real_soundfile_cls = sf.SoundFile
        open_count = {"n": 0}

        class _FlakySoundFile:
            """Real SoundFile for the first two opens (the metadata probe at
            stream_normal.py:163 and chunk 0's read); raises after."""
            def __init__(self, filepath, *args, **kwargs):
                open_count["n"] += 1
                if open_count["n"] > 2:
                    raise RuntimeError("simulated read failure")
                self._real = real_soundfile_cls(filepath, *args, **kwargs)

            def __enter__(self):
                return self._real.__enter__()

            def __exit__(self, *exc_info):
                return self._real.__exit__(*exc_info)

        # #5032 moved the per-chunk read into core.stream_normal_chunks; the
        # metadata read stays in core.stream_normal. Patch both so the flaky
        # SoundFile covers the whole path, as it did when they were one module.
        with patch("core.stream_normal.sf.SoundFile", _FlakySoundFile), \
             patch("core.stream_normal_chunks.sf.SoundFile", _FlakySoundFile):
            await controller.stream_normal_audio(track_id=TRACK_ID, websocket=ws)

        end_msgs = [m for m in sent if m.get("type") == "audio_stream_end"]
        assert end_msgs, "Expected an audio_stream_end message"
        end_data = end_msgs[0]["data"]

        assert end_data["reason"] != "completed"
        assert end_data["reason"] == "errored"
        # Only chunk 0 was delivered — a full CHUNK_DURATION read (150 frames
        # at 10Hz), not the full 300-frame file.
        assert end_data["total_samples"] == 150
        assert 0 < end_data["total_samples"] < 300
