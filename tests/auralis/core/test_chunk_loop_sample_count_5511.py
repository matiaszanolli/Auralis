"""
Regression: chunk-loop sample-count invariants survive python -O (#5511)

The chunk loop's two sample-count checks — the #3700 DSP length invariant
and the #2515 seam-drift guard — were bare ``assert`` statements, compiled
out under ``python -O`` / ``PYTHONOPTIMIZE``. A future DSP length
regression would then silently misalign the output at a seam instead of
raising. #2735 converted the backend stream paths and #5533 the
post-limiter sites; both sites here are now
``if ...: raise RuntimeError(...)``.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.simple_mastering import SimpleMasteringPipeline

_ROOT = Path(__file__).resolve().parents[3]

SR = 44100
CHANNELS = 2
CHUNK_SEC = 1           # 1-second chunks -> easy to reason about counts
CROSSFADE_SEC = 0.02    # 20 ms crossfade


def _make_pipeline() -> SimpleMasteringPipeline:
    config = SimpleMasteringConfig(
        CHUNK_DURATION_SEC=CHUNK_SEC,
        CROSSFADE_DURATION_SEC=CROSSFADE_SEC,
    )
    pipeline = SimpleMasteringPipeline(config=config)
    # Same pattern as test_prev_tail_corruption_guard.py: set the private
    # attribute behind the read-only fingerprint_service property.
    fp_service = MagicMock()
    fp_service.get_or_compute.return_value = {
        'lufs': -14.0, 'crest_db': 6.0, 'bass_mid_ratio': 0.8,
        'tempo_bpm': 120.0, 'spectral_centroid': 3000.0,
    }
    pipeline._fingerprint_service = fp_service
    return pipeline


def _write_sine(path: Path, duration_sec: float) -> None:
    t = np.linspace(0, duration_sec, int(SR * duration_sec), endpoint=False)
    wave = (np.sin(2 * np.pi * 440.0 * t) * 0.5).astype(np.float32)
    sf.write(str(path), np.stack([wave, wave], axis=1), SR, subtype='PCM_24')


def test_invariants_are_raises_not_asserts():
    """Both in-loop checks must be raises (which -O cannot strip)."""
    src = (_ROOT / "auralis/core/mastering_chunk_loop.py").read_text()
    assert "assert processed_chunk.shape[1]" not in src
    assert "assert write_region.shape[1]" not in src
    assert 'raise RuntimeError(\n                        f"DSP sample-count violation' in src
    assert 'raise RuntimeError(\n                                    f"Crossfade write_region mismatch' in src


def test_short_chunk_raises_runtime_error():
    """A _process() that drops one sample must abort the render with
    RuntimeError — the #3700 invariant — even under python -O, because the
    check no longer compiles to a bytecode no-op."""
    pipeline = _make_pipeline()
    calls = [0]
    original_process = pipeline._process

    def short_second_chunk(chunk, *args, **kwargs):
        idx = calls[0]
        calls[0] += 1
        processed, info = original_process(chunk, *args, **kwargs)
        if idx == 1:
            return processed[:, :-1], info  # drop one sample from chunk 1
        return processed, info

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.wav"
        output_path = Path(tmp) / "output.wav"
        _write_sine(input_path, 2.5)  # 3 chunks: the failure lands mid-render

        with patch.object(pipeline, "_process", side_effect=short_second_chunk):
            with pytest.raises(RuntimeError, match="DSP sample-count violation"):
                pipeline.master_file(str(input_path), str(output_path), verbose=False)

    # The render actually reached the second chunk before aborting, and the
    # staged partial output was cleaned up (#5109), not left at output_path.
    assert calls[0] >= 2
    assert not output_path.exists()
