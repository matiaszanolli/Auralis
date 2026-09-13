"""Regression: total_chunks can never exceed the decode budget (#5312).

``load_audio_metadata()`` fed ``content_chunk_count()`` whatever duration the
container header claimed. A forged/corrupt duration (bogus Xing/VBRI frame
count) produced a ``total_chunks`` in the thousands; the enhanced/seek chunk
pumps iterate ``range(processor.total_chunks)``, so every chunk past real EOF
cost a DSP render, a cache write and an ERROR+WARNING log pair.

The primary fix caps the probe itself (see
tests/auralis/io/test_probe_duration_cap_5312.py). This file covers the
independent backstop: even if a future caller hands in an uncapped duration,
the chunk count stays bounded, so the stream terminates.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.io import loader as io_loader
from core.chunk_boundaries import content_chunk_count
from core.chunk_metadata import load_audio_metadata

# 100 hours claimed by the header, ~3 minutes of real audio in the file.
FORGED_DURATION = 360_000.0


def _ceiling() -> int:
    return content_chunk_count(float(io_loader.MAX_DURATION_SECONDS))


class TestForgedDurationIsClamped:
    def test_probe_path_chunk_count_is_bounded(self):
        meta = {
            "sample_rate": 44100,
            "channels": 2,
            "duration_seconds": FORGED_DURATION,
        }
        with (
            patch("core.chunk_metadata.get_audio_info", return_value=meta),
            patch("core.chunk_metadata.load_audio") as m_load,
        ):
            result = load_audio_metadata("/library/forged.mp3")

        m_load.assert_not_called()
        assert result.total_chunks == _ceiling()
        # The unbounded value is what drove the runaway loop.
        assert result.total_chunks < content_chunk_count(FORGED_DURATION)

    def test_full_decode_fallback_chunk_count_is_bounded(self):
        """The fallback path computes its own count — it needs the same bound."""
        audio = np.zeros((10, 2), dtype=np.float32)
        with (
            patch("core.chunk_metadata.get_audio_info",
                  return_value={"error": "probe refused"}),
            patch("core.chunk_metadata.load_audio", return_value=(audio, 1)),
            # A sample rate of 1 makes 10 samples read as 10 s; monkeypatching the
            # budget below that is the cheap way to exercise the same clamp here.
            patch.object(io_loader, "MAX_DURATION_SECONDS", 6),
        ):
            result = load_audio_metadata("/library/forged.mp3")

        assert result.total_chunks == content_chunk_count(6.0)

    def test_ordinary_duration_is_not_clamped(self):
        meta = {"sample_rate": 48000, "channels": 2, "duration_seconds": 212.5}
        with (
            patch("core.chunk_metadata.get_audio_info", return_value=meta),
            patch("core.chunk_metadata.load_audio"),
        ):
            result = load_audio_metadata("/library/song.mp3")

        assert result.total_chunks == content_chunk_count(212.5)
        assert result.total_duration == pytest.approx(212.5)

    def test_clamp_is_logged_so_the_forgery_is_diagnosable(self, caplog):
        meta = {
            "sample_rate": 44100,
            "channels": 2,
            "duration_seconds": FORGED_DURATION,
        }
        with (
            patch("core.chunk_metadata.get_audio_info", return_value=meta),
            patch("core.chunk_metadata.load_audio"),
            caplog.at_level("WARNING", logger="core.chunked_processor"),
        ):
            load_audio_metadata("/library/forged.mp3")

        assert any("clamping" in r.message for r in caplog.records)


class TestStreamTerminatesWithinBounds:
    """Test-plan item 2: the chunk pump ends, rather than running to a forged count."""

    def test_chunk_pump_over_a_forged_track_is_bounded(self):
        meta = {
            "sample_rate": 44100,
            "channels": 2,
            "duration_seconds": FORGED_DURATION,
        }
        with (
            patch("core.chunk_metadata.get_audio_info", return_value=meta),
            patch("core.chunk_metadata.load_audio"),
        ):
            result = load_audio_metadata("/library/forged.mp3")

        # Stand-in for stream_enhanced_chunks / stream_seek_chunks, both of
        # which iterate range(processor.total_chunks).
        rendered = list(range(result.total_chunks))
        assert len(rendered) <= _ceiling()
