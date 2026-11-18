"""Regression for #6434: a failed durable chunk-cache write must not fail the chunk.

``render_chunk`` persisted the rendered segment inside the same ``try`` as the DSP, so ENOSPC
(a full or RAM-backed temp root), a read-only directory or a quota error landed in
``except Exception``: the stream's leased processor was discarded and the error re-raised, and
the chunk was reported failed although the PCM array the stream sends already existed.
The cache is an optimisation; the write is now best-effort and only the DSP can fail the chunk.

:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import errno
import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import core.chunked_processor as cp
from core.chunk_render_miss import render_chunk
from core.encoding import WAVEncoderError

SEGMENT = np.linspace(-0.5, 0.5, 2000, dtype=np.float32).reshape(-1, 2)


def _processor(encode_error: Exception | None) -> MagicMock:
    processor = MagicMock()
    processor.sample_rate = 44100
    processor.preset = "adaptive"
    processor._cancel_event = None
    processor._process_chunk_core.return_value = SEGMENT
    processor._smooth_level_transition.side_effect = lambda audio, _index: audio
    processor._wav_encoder.encode_and_save_from_path.side_effect = encode_error
    return processor


@pytest.mark.parametrize(
    "failure",
    [OSError(errno.ENOSPC, "No space left on device"), PermissionError("read-only"), WAVEncoderError("boom")],
    ids=["enospc", "permission", "encoder-error"],
)
def test_a_failed_cache_write_returns_the_rendered_audio_and_keeps_the_processor(failure, caplog):
    processor = _processor(failure)

    with patch("core.chunk_render_miss._invalidate_after_post_dsp_failure") as invalidate:
        with caplog.at_level(logging.WARNING, logger="core.chunked_processor"):
            path, audio = render_chunk(processor, 3)

    assert path == ""
    np.testing.assert_array_equal(audio, SEGMENT)
    invalidate.assert_not_called()
    processor._path_cache.store.assert_not_called()
    assert processor._dsp_state_advanced is False
    assert any("was not cached" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


def test_a_successful_write_is_unchanged():
    processor = _processor(None)
    processor._wav_encoder.encode_and_save_from_path.return_value = Path("/tmp/chunk_3.wav")

    path, audio = render_chunk(processor, 3)

    assert path == "/tmp/chunk_3.wav"
    np.testing.assert_array_equal(audio, SEGMENT)
    processor._path_cache.store.assert_called_once_with(3, Path("/tmp/chunk_3.wav"))


def test_a_dsp_failure_still_raises_and_discards_the_processor():
    processor = _processor(None)
    processor._process_chunk_core.side_effect = ValueError("dsp blew up")

    with patch("core.chunk_render_miss._invalidate_after_post_dsp_failure") as invalidate:
        with pytest.raises(ValueError, match="dsp blew up"):
            render_chunk(processor, 3)

    invalidate.assert_called_once()


def test_non_storage_encode_errors_are_not_swallowed():
    """NaN audio is a DSP defect, not a storage problem: it must still fail the chunk."""
    processor = _processor(ValueError("Audio contains non-finite values (NaN/Inf)"))

    with patch("core.chunk_render_miss._invalidate_after_post_dsp_failure") as invalidate:
        with pytest.raises(ValueError, match="non-finite"):
            render_chunk(processor, 3)

    invalidate.assert_called_once()


def test_a_real_processor_streams_every_chunk_when_the_cache_write_fails(tmp_path, monkeypatch):
    rate = 8000
    path = tmp_path / "tone.wav"
    sf.write(str(path), np.zeros((rate * 20, 2), dtype=np.float32), rate, subtype="FLOAT")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    processor = cp.ChunkedAudioProcessor(track_id=1, filepath=str(path), preset=None)
    try:
        with patch(
            "core.encoding.wav_encoder.atomic_save_audio",
            side_effect=OSError(errno.ENOSPC, "No space left on device"),
        ):
            results = [processor.process_chunk(i, locked=True) for i in range(processor.total_chunks)]
    finally:
        processor.close()

    assert [p for p, _ in results] == [""] * processor.total_chunks
    assert sum(len(audio) for _, audio in results) == rate * 20
