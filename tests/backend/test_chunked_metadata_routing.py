"""
Regression: chunked metadata must use ffprobe, not a full decode (#4497)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ChunkedAudioProcessor._load_metadata()`` opened ``sf.SoundFile()`` directly,
which libsndfile cannot do for FFmpeg-only formats (mp3/m4a/aac/ogg/wma/opus).
The open raised and the ``except`` fell back to ``load_audio()`` — a full
FFmpeg conversion + full float32 decode — merely to read duration / sample rate
/ channels, at the start of every chunked-playback session for the dominant
library format. The fix routes by extension via ``unified_loader.get_audio_info``
(a millisecond ffprobe for FFmpeg formats), reserving the full decode for a
genuine probe failure.

These tests exercise ``_load_metadata()`` in isolation (via ``__new__`` so the
heavy constructor is skipped) with ``get_audio_info`` / ``load_audio`` patched.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunked_processor import ChunkedAudioProcessor


def _bare_processor(filepath: str) -> ChunkedAudioProcessor:
    """Build just enough of a processor to call _load_metadata()."""
    proc = ChunkedAudioProcessor.__new__(ChunkedAudioProcessor)
    proc.filepath = filepath
    proc.sample_rate = None
    proc.total_duration = None
    proc.total_chunks = None
    proc.channels = None
    return proc


class TestChunkedMetadataRouting:
    def test_ffmpeg_format_uses_probe_not_full_decode(self):
        """An mp3 must read metadata via get_audio_info, never load_audio()."""
        proc = _bare_processor("/library/song.mp3")

        meta = {
            "sample_rate": 48000,
            "channels": 2,
            "duration_seconds": 212.5,
        }
        with (
            patch("core.chunked_processor.get_audio_info", return_value=meta) as m_info,
            patch("core.chunked_processor.load_audio") as m_load,
        ):
            proc._load_metadata()

        m_info.assert_called_once_with("/library/song.mp3")
        m_load.assert_not_called()  # no full decode for metadata
        assert proc.sample_rate == 48000
        assert proc.channels == 2
        assert proc.total_duration == pytest.approx(212.5)
        assert proc.total_chunks is not None and proc.total_chunks > 0

    def test_native_format_metadata_via_probe(self):
        """A wav also flows through get_audio_info (which uses sf.info)."""
        proc = _bare_processor("/library/track.wav")
        meta = {"sample_rate": 44100, "channels": 1, "duration_seconds": 10.0}
        with (
            patch("core.chunked_processor.get_audio_info", return_value=meta),
            patch("core.chunked_processor.load_audio") as m_load,
        ):
            proc._load_metadata()

        m_load.assert_not_called()
        assert proc.sample_rate == 44100
        assert proc.channels == 1
        assert proc.total_duration == pytest.approx(10.0)

    def test_probe_failure_falls_back_to_full_decode(self):
        """Only a genuine probe failure falls back to load_audio()."""
        proc = _bare_processor("/library/broken.mp3")
        # Stereo (frames, channels) — the samples-first convention load_audio uses.
        fake_audio = np.zeros((88200, 2), dtype=np.float32)
        with (
            patch("core.chunked_processor.get_audio_info",
                  return_value={"error": "ffprobe failed"}),
            patch("core.chunked_processor.load_audio",
                  return_value=(fake_audio, 44100)) as m_load,
        ):
            proc._load_metadata()

        m_load.assert_called_once()
        assert proc.sample_rate == 44100
        assert proc.channels == 2                 # shape[1], not the old ternary
        assert proc.total_duration == pytest.approx(88200 / 44100)

    def test_fallback_mono_channels_correct(self):
        """#3881: the fallback must report 1 channel for a mono (1-D) decode."""
        proc = _bare_processor("/library/mono.mp3")
        mono_audio = np.zeros(44100, dtype=np.float32)  # 1-D
        with (
            patch("core.chunked_processor.get_audio_info",
                  return_value={"error": "probe failed"}),
            patch("core.chunked_processor.load_audio",
                  return_value=(mono_audio, 44100)),
        ):
            proc._load_metadata()

        assert proc.channels == 1
        assert proc.total_duration == pytest.approx(1.0)
