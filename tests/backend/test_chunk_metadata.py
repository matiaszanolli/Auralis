"""
Direct unit tests for core.chunk_metadata (#4245 extraction)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``load_audio_metadata()`` was extracted verbatim from
``ChunkedAudioProcessor._load_metadata()``. Behavioral coverage of the
probe-vs-fallback routing already exists in test_chunked_metadata_routing.py
(exercised through the processor's ``_load_metadata()`` wrapper) — these
tests instead call the extracted function directly, in isolation, with no
``ChunkedAudioProcessor`` involved at all.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_metadata import AudioMetadata, load_audio_metadata


class TestLoadAudioMetadataProbePath:
    def test_probe_success_returns_metadata(self):
        from core.chunk_boundaries import content_chunk_count

        meta = {"sample_rate": 48000, "channels": 2, "duration_seconds": 212.5}
        with (
            patch("core.chunk_metadata.get_audio_info", return_value=meta) as m_info,
            patch("core.chunk_metadata.load_audio") as m_load,
        ):
            result = load_audio_metadata("/library/song.mp3")

        m_info.assert_called_once_with("/library/song.mp3")
        m_load.assert_not_called()
        assert result == AudioMetadata(
            sample_rate=48000,
            channels=2,
            total_duration=212.5,
            total_chunks=content_chunk_count(212.5),
        )

    def test_result_is_frozen_dataclass(self):
        meta = {"sample_rate": 44100, "channels": 1, "duration_seconds": 5.0}
        with (
            patch("core.chunk_metadata.get_audio_info", return_value=meta),
            patch("core.chunk_metadata.load_audio"),
        ):
            result = load_audio_metadata("/library/track.wav")

        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            result.sample_rate = 1  # type: ignore[misc]


class TestLoadAudioMetadataFallbackPath:
    def test_probe_error_key_falls_back_to_full_decode(self):
        fake_audio = np.zeros((88200, 2), dtype=np.float32)  # stereo, samples-first
        with (
            patch("core.chunk_metadata.get_audio_info", return_value={"error": "ffprobe failed"}),
            patch("core.chunk_metadata.load_audio", return_value=(fake_audio, 44100)) as m_load,
        ):
            result = load_audio_metadata("/library/broken.mp3")

        m_load.assert_called_once()
        assert result.sample_rate == 44100
        assert result.channels == 2
        assert result.total_duration == pytest.approx(88200 / 44100)

    def test_missing_sample_rate_key_falls_back(self):
        fake_audio = np.zeros(44100, dtype=np.float32)  # mono, 1-D
        with (
            patch("core.chunk_metadata.get_audio_info", return_value={"channels": 1}),
            patch("core.chunk_metadata.load_audio", return_value=(fake_audio, 44100)) as m_load,
        ):
            result = load_audio_metadata("/library/mono.mp3")

        m_load.assert_called_once()
        assert result.channels == 1  # #3881: mono (1-D) must not be mislabelled
        assert result.total_duration == pytest.approx(1.0)

    def test_total_chunks_matches_content_chunk_count(self):
        from core.chunk_boundaries import content_chunk_count

        meta = {"sample_rate": 44100, "channels": 2, "duration_seconds": 42.0}
        with (
            patch("core.chunk_metadata.get_audio_info", return_value=meta),
            patch("core.chunk_metadata.load_audio"),
        ):
            result = load_audio_metadata("/library/track.flac")

        assert result.total_chunks == content_chunk_count(42.0)
