"""Normal-path seek delivers audio from the requested position (#4560).

The normal (unprocessed) streaming path located the containing chunk correctly
and then streamed that chunk FROM ITS START, never trimming to the requested
position. It compensated on paper by advertising `seek_offset` in
`audio_stream_start` — but no client ever consumed that field (the only frontend
hit was the type declaration), so audio restarted up to CHUNK_DURATION (15 s)
BEFORE the requested position while the UI jumped to the requested position.

That made every normal-mode seek, and every WebSocket reconnect-resume during
normal playback (`replayQueueAndResume` re-issues `play_normal` at the current
position, #3185/#3755), replay already-heard audio.

The enhanced path already trims server-side (`stream_seek.py:233-235`), so the
fix makes the server authoritative on both paths. Only one side may trim: a
client-side trim added on top would double-skip.

The fixtures below use a ramp-encoded WAV — sample N holds value N — so the
first delivered sample decodes directly to a source frame index.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController  # noqa: E402
from core import stream_normal  # noqa: E402

TRACK_ID = 1
SAMPLE_RATE = 44100
DURATION_S = 60
CHUNK_DURATION = 15.0


@pytest.fixture(scope="module")
def ramp_wav(tmp_path_factory) -> str:
    """A 60 s mono WAV where frame N holds the value N (as float32)."""
    path = tmp_path_factory.mktemp("seek") / "ramp.wav"
    frames = SAMPLE_RATE * DURATION_S
    # float32 holds integers exactly up to 2**24; 60 s * 44100 = 2.6 M frames.
    ramp = np.arange(frames, dtype=np.float32)
    sf.write(str(path), ramp, SAMPLE_RATE, subtype="FLOAT")
    return str(path)


def _make_ws() -> Mock:
    ws = Mock()
    ws.client_state = Mock()
    ws.client_state.name = "CONNECTED"
    ws.send_text = AsyncMock()
    ws.send_bytes = AsyncMock()
    return ws


def _make_factory(filepath: str) -> Mock:
    factory = Mock(spec=["tracks", "fingerprints"])
    track = Mock()
    track.id = TRACK_ID
    track.filepath = filepath
    factory.tracks.get_by_id = Mock(return_value=track)
    return factory


async def _stream(filepath: str, start_position: float):
    """Run stream_normal_audio, capturing the PCM handed to _send_pcm_chunk.

    Returns (start_message_data, [chunk_arrays]).
    """
    controller = AudioStreamController()
    controller._get_repository_factory = lambda: _make_factory(filepath)

    sent_chunks: list[np.ndarray] = []
    start_data: dict = {}

    async def _capture_chunk(websocket, pcm_samples, chunk_index, total_chunks, **kwargs):
        sent_chunks.append(np.asarray(pcm_samples).copy())
        return True

    async def _capture_start(websocket, **kwargs):
        start_data.update(kwargs)
        return True

    with (
        patch.object(controller, "_send_pcm_chunk", side_effect=_capture_chunk),
        patch.object(controller, "_send_stream_start", side_effect=_capture_start),
        patch.object(controller, "_send_stream_end", AsyncMock(return_value=True)),
    ):
        await stream_normal.stream_normal_audio(
            controller, TRACK_ID, _make_ws(), start_position=start_position
        )

    return start_data, sent_chunks


def _first_source_frame(chunk: np.ndarray) -> int:
    """The ramp value of the first delivered sample == its source frame index."""
    flat = np.asarray(chunk).reshape(-1)
    return int(round(float(flat[0])))


class TestSeekLandsOnTheRequestedPosition:
    @pytest.mark.parametrize("position", [0, 3, 17, 42])
    @pytest.mark.asyncio
    async def test_first_sample_matches_requested_time(self, ramp_wav, position):
        _, chunks = await _stream(ramp_wav, float(position))

        assert chunks, "no PCM was streamed"
        expected_frame = int(position * SAMPLE_RATE)
        assert _first_source_frame(chunks[0]) == pytest.approx(expected_frame, abs=1), (
            f"seek to {position}s delivered source frame "
            f"{_first_source_frame(chunks[0])}, expected {expected_frame} — "
            f"the first chunk was not trimmed to the requested position (#4560)"
        )

    @pytest.mark.asyncio
    async def test_reconnect_resume_delivers_nothing_earlier(self, ramp_wav):
        """A resume at 42 s must not replay audio from before 42 s."""
        position = 42.0
        _, chunks = await _stream(ramp_wav, position)

        earliest = _first_source_frame(chunks[0])
        assert earliest >= int(position * SAMPLE_RATE) - 1, (
            f"resume replayed {(int(position * SAMPLE_RATE) - earliest) / SAMPLE_RATE:.1f}s "
            f"of already-heard audio"
        )

    @pytest.mark.asyncio
    async def test_position_zero_streams_from_sample_zero_untrimmed(self, ramp_wav):
        """No seek → no trim, and the first chunk is full length."""
        start_data, chunks = await _stream(ramp_wav, 0.0)

        assert _first_source_frame(chunks[0]) == 0
        assert len(chunks[0]) == int(CHUNK_DURATION * SAMPLE_RATE)
        # start_chunk/seek_* are omitted entirely when not seeking.
        assert "seek_position" not in start_data


class TestChunkGeometryPreserved:
    @pytest.mark.asyncio
    async def test_second_chunk_still_starts_on_its_boundary(self, ramp_wav):
        """Trimming the first chunk must not shift every later chunk.

        The look-ahead read always uses `(chunk_idx + 1) * interval_samples`, so
        boundaries stay aligned; this pins that.
        """
        position = 17.0
        _, chunks = await _stream(ramp_wav, position)

        assert len(chunks) >= 2
        # 17 s lands in chunk 1 (15-30 s); chunk 2 starts at exactly 30 s.
        assert _first_source_frame(chunks[1]) == int(2 * CHUNK_DURATION * SAMPLE_RATE)

    @pytest.mark.asyncio
    async def test_first_chunk_is_shortened_not_padded(self, ramp_wav):
        position = 17.0
        _, chunks = await _stream(ramp_wav, position)

        trim = int(position * SAMPLE_RATE) - int(CHUNK_DURATION * SAMPLE_RATE)
        assert len(chunks[0]) == int(CHUNK_DURATION * SAMPLE_RATE) - trim

    @pytest.mark.asyncio
    async def test_no_sample_is_delivered_twice(self, ramp_wav):
        """The trim must not create an overlap with the following chunk."""
        _, chunks = await _stream(ramp_wav, 17.0)

        first_end = _first_source_frame(chunks[0]) + len(chunks[0])
        assert _first_source_frame(chunks[1]) == first_end


class TestSeekOffsetIsInformationalOnly:
    """#4560 — the field stays on the wire but is no longer load-bearing."""

    @pytest.mark.asyncio
    async def test_seek_offset_still_advertised(self, ramp_wav):
        start_data, _ = await _stream(ramp_wav, 17.0)

        assert start_data["seek_position"] == 17.0
        assert start_data["start_chunk"] == 1
        assert start_data["seek_offset"] == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_server_trim_makes_the_offset_redundant(self, ramp_wav):
        """If a client also trimmed by seek_offset it would double-skip.

        The delivered audio already starts at seek_position, so seek_offset
        describes history, not a remaining client obligation.
        """
        start_data, chunks = await _stream(ramp_wav, 17.0)

        delivered_start_s = _first_source_frame(chunks[0]) / SAMPLE_RATE
        assert delivered_start_s == pytest.approx(start_data["seek_position"], abs=0.001)


class TestTotalDurationIsTheFullTrack:
    """#4431 — total_duration must report the FULL track length, not the
    duration remaining from the seek point.

    Before the fix, a seek to 17s into a 60s track advertised
    total_duration=43 (60 - 17) here, while stream_enhanced.py/stream_seek.py
    advertised the full 60 for the identical scenario — and this same
    function's own total_chunks field was already full/seek-stable (#3768),
    making the reduced total_duration an internal inconsistency even before
    comparing across paths.
    """

    @pytest.mark.asyncio
    async def test_total_duration_is_full_track_length_on_seek(self, ramp_wav):
        start_data, _ = await _stream(ramp_wav, 17.0)

        assert start_data["total_duration"] == pytest.approx(DURATION_S)

    @pytest.mark.asyncio
    async def test_total_duration_is_full_track_length_with_no_seek(self, ramp_wav):
        start_data, _ = await _stream(ramp_wav, 0.0)

        assert start_data["total_duration"] == pytest.approx(DURATION_S)
