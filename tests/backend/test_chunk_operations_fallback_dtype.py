"""
Regression test for fallback-path dtype in chunk_operations.load_chunk_from_file
(#3833).

When soundfile loading fails, the method falls back to load_audio + slice and,
for the start-beyond-EOF and empty-audio edge cases, returns silence via
np.zeros(...). Those calls used to omit dtype= (defaulting to float64), silently
promoting the chunk away from the pipeline's float32 invariant. They now pass
dtype=np.float32 (fixed in 51e26c68); these tests pin that so it can't regress.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_operations import ChunkOperations

SR = 44100


def test_fallback_start_beyond_eof_returns_float32():
    """soundfile fails → load_audio returns a short file → a chunk whose start is
    past EOF yields float32 silence (not float64)."""
    short = np.zeros((100, 2), dtype=np.float32)

    with patch("soundfile.SoundFile", side_effect=RuntimeError("forced fallback")), \
         patch("auralis.io.unified_loader.load_audio", return_value=(short, SR)):
        audio, _start, _end = ChunkOperations.load_chunk_from_file(
            filepath="/tmp/whatever.wav",
            chunk_index=10,          # start ≈ 95 s ≫ 100 samples → beyond EOF
            sample_rate=SR,
            total_duration=None,     # don't cap load_start back to 0
        )

    assert audio.dtype == np.float32, f"fallback silence must stay float32, got {audio.dtype}"
    assert audio.shape == (1, 2)


def test_fallback_empty_audio_returns_float32():
    """soundfile fails and the requested slice is empty → 100 ms of float32
    silence (not float64)."""
    short = np.zeros((100, 2), dtype=np.float32)

    with patch("soundfile.SoundFile", side_effect=RuntimeError("forced fallback")), \
         patch("auralis.io.unified_loader.load_audio", return_value=(short, SR)):
        audio, _start, _end = ChunkOperations.load_chunk_from_file(
            filepath="/tmp/whatever.wav",
            chunk_index=0,
            sample_rate=SR,
            total_duration=0.0,      # forces load_start == load_end → empty slice
        )

    assert audio.dtype == np.float32, f"empty-audio silence must stay float32, got {audio.dtype}"
    assert len(audio) == int(0.1 * SR)
