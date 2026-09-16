"""
Tests for Normal Streaming Without Overlap (#2099)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Normal (unprocessed) streaming must send non-overlapping chunks: #2099 was
audio played twice because chunks were read at an interval shorter than their
length.

These tests drive the real ``core.stream_normal.stream_normal_audio`` over a
real WAV file and inspect the PCM it hands to ``_send_pcm_chunk``. Every
sample of the file holds its own frame index, so the emitted stream can be
compared with the file sample for sample: a duplicated, dropped or shifted
frame shows up as a mismatch (#5094). The suite used to restate the chunk
geometry in local variables and assert those against each other, which could
not fail whatever the streaming code did.

Chunk geometry comes from ``core.chunk_boundaries``, never from literals.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import inspect
import sys
from itertools import pairwise
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import chunk_boundaries, stream_normal, stream_protocol
from core.audio_stream_controller import AudioStreamController
from core.chunk_boundaries import CHUNK_DURATION, CHUNK_INTERVAL

# A low rate keeps the files small; the geometry is rate-independent.
SAMPLE_RATE = 8000
CHUNK_SAMPLES = int(CHUNK_DURATION * SAMPLE_RATE)
TRACK_ID = 2099

# Sample value = frame index / INDEX_SCALE. A power of two keeps the value
# exact in float32 for any index below 2**24, and below 1.0 for any file
# shorter than INDEX_SCALE frames (262 s at SAMPLE_RATE).
INDEX_SCALE = 2**21


def _write_indexed_wav(path: Path, duration: float, channels: int = 2) -> int:
    frames = int(duration * SAMPLE_RATE)
    assert frames < INDEX_SCALE
    ramp = (np.arange(frames, dtype=np.float64) / INDEX_SCALE).astype(np.float32)
    sf.write(str(path), np.repeat(ramp[:, None], channels, axis=1), SAMPLE_RATE, subtype="FLOAT")
    return frames


def _frame_indices(chunk: np.ndarray) -> np.ndarray:
    """Recover the file frame index each emitted sample came from."""
    assert np.array_equal(chunk[:, 0], chunk[:, -1]), "channels were misaligned"
    return np.rint(chunk[:, 0].astype(np.float64) * INDEX_SCALE).astype(np.int64)


async def _stream(path: Path, start_position: float = 0.0) -> list[np.ndarray]:
    """Run the real normal-stream handler and return the chunks it sent."""
    sent: list[np.ndarray] = []

    async def capture(
        _ws: object, *, pcm_samples: np.ndarray, chunk_index: int, total_chunks: int
    ) -> bool:
        sent.append(np.array(pcm_samples, copy=True))
        return True

    controller = AudioStreamController()
    controller._send_stream_start = AsyncMock(return_value=True)
    controller._send_stream_completion = AsyncMock()
    controller._send_error = AsyncMock()
    controller._send_pcm_chunk = capture
    controller._is_websocket_connected = MagicMock(return_value=True)
    track = MagicMock(filepath=str(path))
    factory = MagicMock()
    factory.tracks.get_by_id.return_value = track
    controller._get_repository_factory = MagicMock(return_value=factory)

    with patch.object(stream_normal, "validate_file_path", side_effect=lambda p, **_kw: p), \
         patch.dict(sys.modules, {"routers.system": MagicMock(
             _stream_pause_events={}, _stream_flow_events={})}):
        await stream_normal.stream_normal_audio(
            controller=controller, track_id=TRACK_ID, websocket=MagicMock(),
            start_position=start_position,
        )

    controller._send_error.assert_not_called()
    return sent


def _plan(frames: int, start_position: float = 0.0) -> chunk_boundaries.NormalStreamPlan:
    return chunk_boundaries.normal_stream_plan(frames, SAMPLE_RATE, start_position)


class TestNormalStreamingChunkCalculation:
    """The chunk plan the normal path streams from."""

    async def test_no_overlap_in_chunk_intervals(self, tmp_path: Path) -> None:
        """Each chunk starts on the frame right after the previous one ends."""
        path = tmp_path / "t.wav"
        _write_indexed_wav(path, 4 * CHUNK_DURATION)

        chunks = [_frame_indices(c) for c in await _stream(path)]

        assert len(chunks) == 4
        for k, (prev, nxt) in enumerate(pairwise(chunks)):
            assert nxt[0] == prev[-1] + 1, f"chunk {k + 1} does not follow chunk {k}"

    @pytest.mark.parametrize("seconds", [CHUNK_DURATION, 2 * CHUNK_DURATION + 7.3, 11 * CHUNK_DURATION + 1.0])
    async def test_total_duration_matches_file_duration(self, tmp_path: Path, seconds: float) -> None:
        """Delivered audio is exactly the file's length, and the plan counts
        ceil(frames / chunk) chunks for it."""
        path = tmp_path / "t.wav"
        frames = _write_indexed_wav(path, seconds)

        chunks = await _stream(path)

        assert sum(len(c) for c in chunks) == frames
        assert len(chunks) == _plan(frames).total_chunks == int(np.ceil(frames / CHUNK_SAMPLES))

    def test_enhanced_vs_normal_streaming_overlap(self) -> None:
        """The enhanced model advances by CHUNK_INTERVAL (< CHUNK_DURATION);
        the normal plan must advance by the full chunk instead."""
        assert CHUNK_INTERVAL < CHUNK_DURATION, "enhanced path is expected to overlap"

        plan = _plan(10 * CHUNK_SAMPLES)

        assert plan.chunk_duration == CHUNK_DURATION
        assert plan.chunk_samples == CHUNK_SAMPLES
        assert plan.interval_samples == plan.chunk_samples
        assert plan.interval_samples != int(CHUNK_INTERVAL * SAMPLE_RATE)
        assert plan.total_chunks == 10

    def test_no_crossfade_parameter_on_the_send_path(self) -> None:
        """
        Normal streaming applies no crossfade, and neither does any other path
        — so `crossfade_samples` no longer exists on the send API at all
        (#4642).
        """
        params = inspect.signature(stream_protocol.send_pcm_chunk).parameters
        assert 'crossfade_samples' not in params


class TestNormalStreamingAudioDuplication:
    """The emitted stream is the file, once."""

    async def test_no_duplicated_samples_in_chunk_sequence(self, tmp_path: Path) -> None:
        """Concatenated chunks equal the file sample for sample: no frame
        repeated (the #2099 bug), none skipped."""
        path = tmp_path / "t.wav"
        frames = _write_indexed_wav(path, 3 * CHUNK_DURATION + 4.0, channels=1)

        emitted = np.concatenate([_frame_indices(c) for c in await _stream(path)])

        np.testing.assert_array_equal(emitted, np.arange(frames))

    async def test_playback_duration_not_inflated_by_overlap(self, tmp_path: Path) -> None:
        """A 3-minute file plays for 3 minutes. With chunks read every
        CHUNK_INTERVAL instead, it would last about CHUNK_DURATION / CHUNK_INTERVAL
        times longer."""
        path = tmp_path / "t.wav"
        frames = _write_indexed_wav(path, 180.0)

        chunks = await _stream(path)

        assert sum(len(c) for c in chunks) / SAMPLE_RATE == pytest.approx(frames / SAMPLE_RATE)


class TestChunkBoundaryArtifacts:
    """Chunk edges, including the first chunk after a seek."""

    async def test_chunk_boundaries_are_clean(self, tmp_path: Path) -> None:
        """Every chunk but the last is exactly one chunk long and starts on a
        chunk boundary; the last is the true remainder, not padded (#2124)."""
        path = tmp_path / "t.wav"
        frames = _write_indexed_wav(path, 3 * CHUNK_DURATION + 2.5)

        chunks = [_frame_indices(c) for c in await _stream(path)]

        for k, chunk in enumerate(chunks[:-1]):
            assert len(chunk) == CHUNK_SAMPLES
            assert chunk[0] == k * CHUNK_SAMPLES
        assert len(chunks[-1]) == frames - (len(chunks) - 1) * CHUNK_SAMPLES

    async def test_seek_resumes_at_the_position_without_replay(self, tmp_path: Path) -> None:
        """A mid-chunk seek emits from the requested frame, and the next chunk
        is back on its boundary: nothing before the seek point is replayed
        (#4560), nothing after it is duplicated."""
        path = tmp_path / "t.wav"
        frames = _write_indexed_wav(path, 3 * CHUNK_DURATION)
        position = CHUNK_DURATION + 6.25
        seek_frame = int(position * SAMPLE_RATE)

        chunks = [_frame_indices(c) for c in await _stream(path, start_position=position)]

        assert chunks[0][0] == seek_frame
        assert chunks[1][0] == 2 * CHUNK_SAMPLES
        np.testing.assert_array_equal(np.concatenate(chunks), np.arange(seek_frame, frames))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
