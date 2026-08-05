"""Regression tests for propagating partial PCM send failures (#4732)."""

import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController

stream_protocol = importlib.import_module("core.stream_protocol")


def _make_processor() -> MagicMock:
    processor = MagicMock()
    processor.track_id = 42
    processor.preset = "adaptive"
    processor.intensity = 1.0
    processor.sample_rate = 10
    processor.channels = 2
    processor.total_chunks = 3
    processor.chunk_duration = 10.0
    processor.chunk_interval = 10.0
    processor.duration = 30.0
    processor.file_signature = "test-signature"

    async def process_chunk_safe(chunk_idx: int, fast_start: bool = False):
        del fast_start
        return Path(f"/tmp/chunk-{chunk_idx}.wav"), np.zeros((100, 2), dtype=np.float32)

    processor.process_chunk_safe = process_chunk_safe
    return processor


def _make_processed_stream_controller(
    processor: MagicMock,
) -> AudioStreamController:
    controller = AudioStreamController(
        chunked_processor_class=MagicMock(return_value=processor)
    )
    track = MagicMock(filepath="/tmp/test.wav")
    factory = MagicMock()
    factory.tracks.get_by_id.return_value = track
    controller._get_repository_factory = MagicMock(return_value=factory)
    controller._is_websocket_connected = MagicMock(return_value=True)
    controller._send_stream_start = AsyncMock(return_value=True)
    controller._stream_processed_chunk = AsyncMock(side_effect=[True, False])
    controller._send_error = AsyncMock()
    controller._send_stream_end = AsyncMock(return_value=True)
    return controller


def _assert_stopped_after_one_chunk(controller: AudioStreamController) -> None:
    assert controller._stream_processed_chunk.await_count == 2
    assert "Failed to send audio chunk 1" in controller._send_error.await_args.args
    end_kwargs = controller._send_stream_end.await_args.kwargs
    assert end_kwargs["reason"] == "stopped"
    assert end_kwargs["total_samples"] == 100
    assert end_kwargs["duration"] == 10.0


@pytest.mark.asyncio
async def test_send_pcm_chunk_returns_false_when_second_binary_frame_fails():
    controller = MagicMock()
    controller._safe_send = AsyncMock(return_value=True)
    controller._safe_send_bytes = AsyncMock(side_effect=[True, False])

    # More than two 300 KiB frames of flattened float32 PCM.
    pcm = np.zeros(160_000, dtype=np.float32)

    delivered = await stream_protocol.send_pcm_chunk(
        controller, MagicMock(), pcm, chunk_index=0, total_chunks=1
    )

    assert delivered is False
    assert controller._safe_send_bytes.await_count == 2


@pytest.mark.asyncio
async def test_send_pcm_chunk_returns_true_after_every_frame_is_sent():
    controller = MagicMock()
    controller._safe_send = AsyncMock(return_value=True)
    controller._safe_send_bytes = AsyncMock(return_value=True)

    delivered = await stream_protocol.send_pcm_chunk(
        controller,
        MagicMock(),
        np.zeros((100, 2), dtype=np.float32),
        chunk_index=0,
        total_chunks=1,
    )

    assert delivered is True


@pytest.mark.asyncio
async def test_enhanced_stream_stops_without_counting_failed_chunk():
    processor = _make_processor()
    controller = _make_processed_stream_controller(processor)

    with (
        patch("core.stream_enhanced.Path.exists", return_value=True),
        patch.object(
            controller,
            "_check_or_queue_fingerprint",
            new=AsyncMock(return_value=False),
        ),
    ):
        await controller.stream_enhanced_audio(
            track_id=42,
            preset="adaptive",
            intensity=1.0,
            websocket=MagicMock(),
        )

    _assert_stopped_after_one_chunk(controller)


@pytest.mark.asyncio
async def test_seek_stream_stops_without_counting_failed_chunk():
    processor = _make_processor()
    controller = _make_processed_stream_controller(processor)

    with patch("core.stream_seek.Path.exists", return_value=True):
        await controller.stream_enhanced_audio_from_position(
            track_id=42,
            preset="adaptive",
            intensity=1.0,
            websocket=MagicMock(),
            start_position=0.0,
        )

    _assert_stopped_after_one_chunk(controller)


@pytest.mark.asyncio
async def test_normal_stream_stops_without_counting_failed_chunk(tmp_path):
    wav_path = tmp_path / "track.wav"
    sf.write(wav_path, np.zeros((200, 2), dtype=np.float32), samplerate=10)

    controller = AudioStreamController()
    track = MagicMock(filepath=str(wav_path))
    factory = MagicMock()
    factory.tracks.get_by_id.return_value = track
    controller._get_repository_factory = MagicMock(return_value=factory)
    controller._is_websocket_connected = MagicMock(return_value=True)
    controller._send_stream_start = AsyncMock(return_value=True)
    controller._send_pcm_chunk = AsyncMock(side_effect=[True, False])
    controller._send_error = AsyncMock()
    controller._send_stream_end = AsyncMock(return_value=True)

    await controller.stream_normal_audio(track_id=42, websocket=MagicMock())

    assert controller._send_pcm_chunk.await_count == 2
    assert "Failed to send audio chunk 1" in controller._send_error.await_args.args
    end_kwargs = controller._send_stream_end.await_args.kwargs
    assert end_kwargs["reason"] == "stopped"
    assert end_kwargs["total_samples"] == 150
    assert end_kwargs["duration"] == 15.0
