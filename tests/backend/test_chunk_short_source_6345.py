"""Regression for #6345: a source that ends before its probed duration.

The container duration of a lossy file counts encoder priming the decoder
strips: 2112 samples for iTunes AAC, about one frame for MP3. The chunked
renderer sized its geometry from that probe, so

- the last chunk was padded with silence up to the probed length (silence at
  every track end, which breaks gapless playback), and
- when the last chunk is shorter than the context, the penultimate chunk's end
  context is capped at the probed duration; trimming it from the tail of a
  buffer that ended early removed real audio, and the hole was padded mid-track.

The output must reproduce exactly the samples the source holds, no more.

:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_boundary_manager import ChunkBoundaryManager
from core.chunk_file_loading import load_chunk_from_file
from core.chunk_segment_extraction import extract_chunk_segment

SR = 1000
SHORTFALL = 48  # samples the decoder yields fewer than the probe claims (~2112 @ 44.1k)


def _render(probed_duration: float, read_chunk) -> np.ndarray:
    """Identity-DSP chunk pipeline driven by the PROBED duration, as in production."""
    manager = ChunkBoundaryManager(total_duration=probed_duration, sample_rate=SR)
    segments = []
    for index in range(manager.total_chunks):
        trimmed = manager.trim_context(read_chunk(manager, index), index)
        segments.append(extract_chunk_segment(
            processed_chunk=trimmed, chunk_index=index, sample_rate=SR,
            total_chunks=manager.total_chunks, total_duration=probed_duration,
        ))
    return np.vstack(segments)[:, 0]


def _ramp(n: int) -> np.ndarray:
    ramp = np.arange(n, dtype=np.float64)
    return np.column_stack([ramp, ramp])


# 47 s: the last chunk carries 2 s, so the penultimate chunk's end context is
# capped at the probed end. 52 s: the last chunk carries 7 s, nothing capped.
@pytest.mark.parametrize("probed_duration", [12.0, 47.0, 52.0])
def test_short_source_renders_exactly_what_it_holds(probed_duration):
    decoded = _ramp(int(round(probed_duration * SR)) - SHORTFALL)

    def read(manager, index):
        load_start, load_end, _, _ = manager.get_chunk_boundaries_samples(index)
        return decoded[load_start:load_end].copy()  # a read past EOF just stops

    out = _render(probed_duration, read)

    assert len(out) == len(decoded), f"emitted {len(out) - len(decoded):+d} samples vs the source"
    np.testing.assert_array_equal(out, decoded[:, 0])


def test_short_source_file_read_has_no_silence_tail_or_hole(tmp_path):
    """Same, through the real file reader (libsndfile stops at EOF)."""
    probed_duration = 47.0
    decoded = _ramp(int(round(probed_duration * SR)) - SHORTFALL) / 1e5  # keep within [-1, 1]
    path = tmp_path / "short.wav"
    sf.write(path, decoded, SR, subtype="DOUBLE")

    def read(manager, index):
        audio, _, _ = load_chunk_from_file(str(path), index, SR, total_duration=probed_duration)
        return audio.astype(np.float64)

    out = _render(probed_duration, read)

    assert len(out) == len(decoded)
    np.testing.assert_allclose(out, decoded[:, 0], atol=1e-6)
