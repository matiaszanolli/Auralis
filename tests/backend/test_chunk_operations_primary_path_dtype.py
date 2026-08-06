"""Regression test for primary-path dtype in chunk_operations.load_chunk_from_file
(#4794).

soundfile.SoundFile.read() defaults to float64 when dtype= is omitted, so the
primary (non-fallback) load path silently double-precisioned every chunk of
every natively-decodable file — inconsistent with the fallback path
(load_audio, float32) and the silence fallbacks (dtype=np.float32, fixed for
#3833 in test_chunk_operations_fallback_dtype.py). Now the primary read
explicitly passes dtype='float32', always_2d=True.
"""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.chunk_operations import ChunkOperations

SR = 44100


def _write_wav(path: Path, duration_s: float = 2.0, channels: int = 2) -> None:
    samples = int(duration_s * SR)
    audio = np.zeros((samples, channels), dtype=np.float32)
    sf.write(str(path), audio, SR, subtype='FLOAT')


def test_primary_path_returns_float32(tmp_path):
    """The primary sf.SoundFile.read() path must return float32, not the
    soundfile default of float64."""
    wav_path = tmp_path / "chunk_source.wav"
    _write_wav(wav_path)

    audio, _start, _end = ChunkOperations.load_chunk_from_file(
        filepath=str(wav_path),
        chunk_index=0,
        sample_rate=SR,
        total_duration=2.0,
        with_context=False,
    )

    assert audio.dtype == np.float32, f"primary load path must be float32, got {audio.dtype}"
    assert audio.ndim == 2


def test_primary_and_fallback_paths_agree_on_dtype(tmp_path):
    """Loading the same file via the primary path and via the forced fallback
    path must produce the same dtype (#4794 acceptance criterion)."""
    wav_path = tmp_path / "chunk_source.wav"
    _write_wav(wav_path)

    primary_audio, _, _ = ChunkOperations.load_chunk_from_file(
        filepath=str(wav_path),
        chunk_index=0,
        sample_rate=SR,
        total_duration=2.0,
        with_context=False,
    )

    from unittest.mock import patch

    from auralis.io.unified_loader import load_audio
    full_audio, _ = load_audio(str(wav_path), target_sample_rate=SR)

    with patch("soundfile.SoundFile", side_effect=RuntimeError("forced fallback")), \
         patch("auralis.io.unified_loader.load_audio", return_value=(full_audio, SR)):
        fallback_audio, _, _ = ChunkOperations.load_chunk_from_file(
            filepath=str(wav_path),
            chunk_index=0,
            sample_rate=SR,
            total_duration=2.0,
            with_context=False,
        )

    assert primary_audio.dtype == fallback_audio.dtype == np.float32
