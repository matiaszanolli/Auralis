"""Regression tests for unbounded chunk_idx reaching the uncached full-file-decode
fallback (#4342).

get_wav_chunk_path() only enforced chunk_index >= 0, and load_chunk_from_file's
soundfile-seek-past-EOF exception path fell through to a full load_audio()
decode of the entire file just to return 100ms of silence — a small-request ->
large-work amplifier. get_wav_chunk_path() now rejects chunk_index >=
total_chunks up front, and load_chunk_from_file bails out on an empty/inverted
load window before ever attempting a read, so the full-decode fallback is never
reached for an out-of-range index.
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_operations import ChunkOperations
from auralis.io.saver import save as save_audio

SR = 44100


def _create_test_audio(duration_seconds: float, sample_rate: int = SR) -> np.ndarray:
    num_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, num_samples, endpoint=False)
    audio = np.sin(2 * np.pi * 440 * t)
    return np.column_stack([audio, audio])


class TestLoadChunkFromFileBailsOutEarly:
    def test_out_of_range_chunk_index_never_calls_load_audio(self):
        """An out-of-range chunk_index collapses the load window to empty/
        inverted; load_audio (the full-file decode) must never be invoked."""
        with patch("auralis.io.unified_loader.load_audio") as mock_load_audio, \
             patch("soundfile.SoundFile") as mock_soundfile:
            audio, _start, _end = ChunkOperations.load_chunk_from_file(
                filepath="/tmp/whatever.wav",
                chunk_index=10_000,  # grossly beyond any real track
                sample_rate=SR,
                total_duration=120.0,  # a normal 2-minute track
            )

        mock_load_audio.assert_not_called()
        mock_soundfile.assert_not_called()
        assert audio.dtype == np.float32
        assert len(audio) == int(0.1 * SR)

    def test_in_range_chunk_index_still_reads_normally(self):
        """Sanity: a legitimate chunk_index must NOT hit the early bail-out."""
        with patch("soundfile.SoundFile") as mock_soundfile:
            mock_file = mock_soundfile.return_value.__enter__.return_value
            mock_file.read.return_value = np.zeros((44100, 2), dtype=np.float32)

            ChunkOperations.load_chunk_from_file(
                filepath="/tmp/whatever.wav",
                chunk_index=0,
                sample_rate=SR,
                total_duration=120.0,
            )

        mock_soundfile.assert_called_once()


class TestGetWavChunkPathRejectsOutOfRange:
    @pytest.fixture
    def temp_audio_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_raises_value_error_for_chunk_index_beyond_total_chunks(self, temp_audio_dir):
        import core.chunked_processor as cp

        audio = _create_test_audio(2.0)
        filepath = temp_audio_dir / "test_audio.wav"
        save_audio(str(filepath), audio, SR, subtype='PCM_16')

        processor = cp.ChunkedAudioProcessor(
            track_id=1, filepath=str(filepath), preset="adaptive", intensity=1.0
        )
        assert processor.total_chunks == 1

        with patch("auralis.io.unified_loader.load_audio") as mock_load_audio:
            with pytest.raises(ValueError, match="out of range"):
                processor.get_wav_chunk_path(processor.total_chunks + 100)

        mock_load_audio.assert_not_called()

    def test_raises_value_error_for_negative_chunk_index(self, temp_audio_dir):
        import core.chunked_processor as cp

        audio = _create_test_audio(2.0)
        filepath = temp_audio_dir / "test_audio.wav"
        save_audio(str(filepath), audio, SR, subtype='PCM_16')

        processor = cp.ChunkedAudioProcessor(
            track_id=1, filepath=str(filepath), preset="adaptive", intensity=1.0
        )

        with pytest.raises(ValueError, match="out of range"):
            processor.get_wav_chunk_path(-1)

    def test_valid_chunk_index_still_succeeds(self, temp_audio_dir):
        import core.chunked_processor as cp

        audio = _create_test_audio(2.0)
        filepath = temp_audio_dir / "test_audio.wav"
        save_audio(str(filepath), audio, SR, subtype='PCM_16')

        processor = cp.ChunkedAudioProcessor(
            track_id=1, filepath=str(filepath), preset="adaptive", intensity=1.0
        )

        wav_path = processor.get_wav_chunk_path(0)
        assert Path(wav_path).exists()
