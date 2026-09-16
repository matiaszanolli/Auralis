"""
The level-smoothing gain ramp must land in audio the listener hears (#5051)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`process_chunk_core` used to smooth the context-trimmed 15 s buffer, and the
caller then cut the emitted segment out of it. LevelManager places its 50 ms
gain ramp at sample 0 of what it is given, so for every chunk after the first
the ramp sat in the 5 s overlap head that extraction throws away: the emitted
audio started directly at the new gain, a hard step at every smoothed
boundary. The same order made a cache MISS record the RMS of the 15 s buffer
while a cache HIT records the RMS of the emitted bytes.

These tests run a real ChunkedAudioProcessor over a real file, with only the
DSP pipeline replaced by a passthrough, and look at what process_chunk emits.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import chunk_render
from core.audio_processing_pipeline import AudioProcessingPipeline
from core.chunked_processor import ChunkedAudioProcessor
from core.level_manager import GAIN_RAMP_SECONDS, LevelManager

SR = 22050
DURATION = 40.0
# Constant-level stereo "DC" segments: (start seconds, level). Emitted chunks
# are [0,15], [15,25], [25,35], [35,40]. The source is continuous across the
# 15 s boundary (0.4 on both sides), but chunk 1 is much louder on average
# than chunk 0, so the smoother must fire there.
SEGMENTS = [(0.0, 0.1), (13.0, 0.4), (25.0, 0.2)]


@pytest.fixture
def processor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ChunkedAudioProcessor]:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    chunk_render.reset_chunk_levels()

    t = np.arange(int(DURATION * SR)) / SR
    level = np.zeros_like(t)
    for start, value in SEGMENTS:
        level[t >= start] = value
    path = tmp_path / "track.wav"
    sf.write(str(path), np.column_stack([level, level]).astype(np.float32), SR, subtype="FLOAT")

    proc = ChunkedAudioProcessor(
        track_id=5051, filepath=str(path), preset="adaptive", intensity=1.0, chunk_cache={},
    )

    def passthrough(audio: np.ndarray, **_kwargs: Any) -> np.ndarray:
        return audio.copy()

    with patch.object(AudioProcessingPipeline, "process_audio", side_effect=passthrough):
        yield proc
    proc.close()
    chunk_render.reset_chunk_levels()


def _emit(proc: ChunkedAudioProcessor, chunk_index: int) -> np.ndarray:
    _path, audio = proc.process_chunk(chunk_index)
    return audio[:, 0].astype(np.float64)


def test_smoothed_boundary_ramps_instead_of_stepping(processor: ChunkedAudioProcessor) -> None:
    first = _emit(processor, 0)
    second = _emit(processor, 1)
    ramp = round(GAIN_RAMP_SECONDS * SR)

    # The smoother fired: chunk 1 settles well below its 0.4 source level.
    settled = second[ramp:]
    assert np.ptp(settled) < 1e-6
    assert settled[0] < 0.35

    # ...and it gets there through a ramp inside the emitted audio, starting
    # from the gain chunk 0 ended on. The source is 0.4 on both sides of the
    # boundary, so the output is continuous there.
    assert len(np.unique(np.round(second[:ramp], 6))) > 1
    assert second[0] == pytest.approx(first[-1], abs=1e-3)


def test_miss_records_the_level_of_the_emitted_bytes(processor: ChunkedAudioProcessor) -> None:
    """Chunk 2's render window [20,35] is partly 0.4, its emitted segment
    [25,35] is all 0.2. The recorded RMS must describe the emitted segment,
    which is what a cache hit on these bytes records."""
    for index in range(2):
        _emit(processor, index)
    _path, emitted = processor.process_chunk(2)

    recorded = processor._level_manager.current_rms
    assert recorded == pytest.approx(LevelManager().calculate_rms(emitted), abs=0.01)
