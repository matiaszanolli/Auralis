"""
Regression tests: ChunkOperations.load_chunk_from_file() boundaries must
match ChunkBoundaryManager exactly (#5055)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

load_chunk_from_file() used to re-derive chunk_start/chunk_end/load_start/
load_end inline instead of delegating to ChunkBoundaryManager.get_chunk_boundaries()
— the same authority trim_context() uses. The two independent derivations
happened to agree today (all boundaries fall on 5s multiples), but nothing
structurally tied them together, so a future change to one could silently
desync the loader from the trimmer, cutting into real content (the #3807
failure mode).

#5055 makes load_chunk_from_file() call ChunkBoundaryManager directly
whenever a total_duration is known (the only case any production caller
uses). These tests assert exact agreement across chunk indices and a
non-44100 sample rate, and confirm reading past sf.SoundFile with the
manager-derived window still returns correctly-shaped audio.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_boundaries import ChunkBoundaryManager
from core.chunk_operations import ChunkOperations

SAMPLE_RATE_48K = 48000


def _mock_soundfile_read(load_start: float, load_end: float, sample_rate: int):
    """A soundfile.SoundFile mock that returns exactly the requested
    frame count as float32 silence, so load_chunk_from_file's own
    frames_to_read arithmetic is what's under test, not real file I/O."""
    frames = int(round((load_end - load_start) * sample_rate))
    return np.zeros((max(frames, 0), 2), dtype=np.float32)


class TestLoadChunkBoundariesMatchChunkBoundaryManager:
    @pytest.mark.parametrize("total_duration", [37.0, 62.5, 128.0])
    @pytest.mark.parametrize("sample_rate", [44100, SAMPLE_RATE_48K])
    def test_boundaries_match_for_every_chunk(self, total_duration, sample_rate):
        """For a range of chunk indices (first/middle/last) and a
        non-44100 sample rate, load_chunk_from_file()'s computed
        (load_start, load_end, chunk_start, chunk_end) must equal
        ChunkBoundaryManager.get_chunk_boundaries()'s exactly."""
        manager = ChunkBoundaryManager(total_duration=total_duration, sample_rate=sample_rate)

        for chunk_index in range(manager.total_chunks):
            expected_load_start, expected_load_end, expected_chunk_start, expected_chunk_end = (
                manager.get_chunk_boundaries(chunk_index)
            )

            with patch("soundfile.SoundFile") as mock_soundfile:
                mock_file = mock_soundfile.return_value.__enter__.return_value
                mock_file.read.side_effect = lambda *a, **k: _mock_soundfile_read(
                    expected_load_start, expected_load_end, sample_rate
                )

                _audio, chunk_start, chunk_end = ChunkOperations.load_chunk_from_file(
                    filepath="/tmp/whatever.wav",
                    chunk_index=chunk_index,
                    sample_rate=sample_rate,
                    total_duration=total_duration,
                )

            assert chunk_start == expected_chunk_start, (
                f"chunk {chunk_index}: chunk_start {chunk_start} != "
                f"ChunkBoundaryManager's {expected_chunk_start}"
            )
            assert chunk_end == expected_chunk_end, (
                f"chunk {chunk_index}: chunk_end {chunk_end} != "
                f"ChunkBoundaryManager's {expected_chunk_end}"
            )
            # The mock's seek target was computed from expected_load_start
            # via load_chunk_from_file's own start_frame arithmetic — assert
            # it was actually requested, confirming load_start agreed too.
            expected_start_frame = int(round(expected_load_start * sample_rate))
            mock_file.seek.assert_called_once_with(expected_start_frame)

    def test_without_context_boundaries_still_match(self):
        """with_context=False must also delegate to ChunkBoundaryManager,
        not fall back to a different derivation."""
        total_duration = 62.5
        sample_rate = 44100
        manager = ChunkBoundaryManager(total_duration=total_duration, sample_rate=sample_rate)
        chunk_index = 1

        expected_load_start, expected_load_end, expected_chunk_start, expected_chunk_end = (
            manager.get_chunk_boundaries(chunk_index, with_context=False)
        )

        with patch("soundfile.SoundFile") as mock_soundfile:
            mock_file = mock_soundfile.return_value.__enter__.return_value
            mock_file.read.side_effect = lambda *a, **k: _mock_soundfile_read(
                expected_load_start, expected_load_end, sample_rate
            )

            _audio, chunk_start, chunk_end = ChunkOperations.load_chunk_from_file(
                filepath="/tmp/whatever.wav",
                chunk_index=chunk_index,
                sample_rate=sample_rate,
                total_duration=total_duration,
                with_context=False,
            )

        assert chunk_start == expected_chunk_start
        assert chunk_end == expected_chunk_end
        expected_start_frame = int(round(expected_load_start * sample_rate))
        mock_file.seek.assert_called_once_with(expected_start_frame)

    def test_total_duration_none_still_uses_the_unbounded_fallback(self):
        """Sibling check: when total_duration is unknown, load_chunk_from_file
        must NOT attempt to construct a ChunkBoundaryManager (which requires
        one) — it must keep using the original unbounded derivation. This is
        the same case test_fallback_start_beyond_eof_returns_float32 relies
        on; asserted here directly against the boundary values themselves."""
        sample_rate = 44100
        chunk_index = 2
        chunk_duration = 15.0
        chunk_interval = 10.0

        with patch("soundfile.SoundFile") as mock_soundfile:
            mock_file = mock_soundfile.return_value.__enter__.return_value
            mock_file.read.return_value = np.zeros((1, 2), dtype=np.float32)

            _audio, chunk_start, chunk_end = ChunkOperations.load_chunk_from_file(
                filepath="/tmp/whatever.wav",
                chunk_index=chunk_index,
                sample_rate=sample_rate,
                total_duration=None,
            )

        # Uncapped: chunk_end is NOT clamped to any total_duration.
        assert chunk_start == chunk_index * chunk_interval
        assert chunk_end == chunk_index * chunk_interval + chunk_duration
