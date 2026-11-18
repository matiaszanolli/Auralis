"""Regression for #6427: the decoder holds less than the probe by more than the last chunk's remainder.

``content_chunk_count`` allocates a trailing chunk for any ``T mod 10 > 5``. When
the decoder's shortfall (encoder priming, or the 1% / 0.5 s tolerance
``can_seek_natively`` accepts) is at least that chunk's real content, the chunk
holds no decoded audio: its segment is an empty ``(0, ch)`` array.
``WAVEncoder.encode_and_save`` raised ``ValueError("Cannot encode empty audio
array")``, the final chunk failed on every replay, the stream ended
``reason="errored"`` and queue auto-advance never fired. The penultimate chunk
also had the missing samples padded on as silence.

:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import core.chunk_metadata as chunk_metadata
import core.chunked_processor as cp
from tests.backend.test_chunk_short_source_6345 import SHORTFALL, SR, _ramp, _render

PROBED = 25.03  # T mod 10 = 5.03 > 5: a trailing chunk is allocated for 0.03 s
# SHORTFALL (48 samples = 0.048 s) exceeds that 0.03 s remainder: the last chunk is empty.


def _decoded() -> np.ndarray:
    return _ramp(int(round(PROBED * SR)) - SHORTFALL)


def _read(decoded):
    def read(manager, index):
        load_start, load_end, _, _ = manager.get_chunk_boundaries_samples(index)
        return decoded[load_start:load_end].copy()

    return read


def test_empty_last_segment_is_returned_not_raised():
    decoded = _decoded()
    out = _render(PROBED, _read(decoded))  # extract_chunk_segment raised nothing

    # Every decoded sample, and no silence padded onto the penultimate chunk.
    assert len(out) == len(decoded)
    np.testing.assert_array_equal(out, decoded[:, 0])


def test_the_last_segment_really_is_empty():
    from core.chunk_boundary_manager import ChunkBoundaryManager
    from core.chunk_segment_extraction import extract_chunk_segment

    manager = ChunkBoundaryManager(total_duration=PROBED, sample_rate=SR)
    assert manager.total_chunks == 3
    last = manager.total_chunks - 1
    trimmed = manager.trim_context(_read(_decoded())(manager, last), last)

    segment = extract_chunk_segment(
        trimmed, last, SR, total_chunks=manager.total_chunks, total_duration=PROBED
    )

    assert segment.shape == (0, 2)


@pytest.fixture
def short_wav(tmp_path, monkeypatch):
    """A 24.98 s file whose container claims 25.03 s (T mod 10 = 5.03)."""
    rate = 8000
    path = tmp_path / "short.wav"
    sf.write(str(path), np.zeros((int(24.98 * rate), 2), dtype=np.float32), rate, subtype="FLOAT")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))  # the chunk cache lives here
    real_info = chunk_metadata.get_audio_info

    def probe(filepath):
        return {**real_info(filepath), "duration_seconds": PROBED}

    with patch.object(chunk_metadata, "get_audio_info", side_effect=probe):
        yield str(path), rate


def test_every_chunk_of_a_short_source_renders_and_emits_exactly_what_it_holds(short_wav):
    path, rate = short_wav
    processor = cp.ChunkedAudioProcessor(track_id=1, filepath=path, preset=None)
    try:
        assert processor.total_chunks == 3
        results = [processor.process_chunk(i, locked=True) for i in range(processor.total_chunks)]
    finally:
        processor.close()

    emitted = sum(len(audio) for _path, audio in results)
    assert emitted == int(24.98 * rate)  # decoded length: no padding, nothing lost
    last_path, last_audio = results[-1]
    assert last_audio.shape[0] == 0 and last_path == ""  # no file, nothing cached for the empty tail
    assert all(path_ for path_, _ in results[:-1])  # real chunks are still persisted
