"""
Tests for zero-length crossfade boundary guard in SimpleMasteringPipeline
(issue #2157)

Verifies that:
- head_len == 0 is handled gracefully (no silent sample drop)
- Output sample count == input sample count for edge-case chunk sizes
- Normal crossfade (head_len > 0) continues to work correctly
- Single-chunk audio is unaffected
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest
import soundfile as sf

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.simple_mastering import SimpleMasteringPipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SR = 44100  # Fast enough, avoids DSP overhead in tests


def _make_config(crossfade_sec: float = 0.0, chunk_sec: int = 1) -> SimpleMasteringConfig:
    """Return a fast config with controllable crossfade."""
    config = SimpleMasteringConfig()
    config.CROSSFADE_DURATION_SEC = crossfade_sec
    config.CHUNK_DURATION_SEC = chunk_sec
    return config


def _write_sine(path: str, n_samples: int, channels: int = 2) -> None:
    """Write a simple sine WAV file."""
    t = np.linspace(0, n_samples / SR, n_samples, endpoint=False)
    mono = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    if channels == 2:
        sf.write(path, np.column_stack([mono, mono]), SR)
    else:
        sf.write(path, mono, SR)


def _fake_fingerprint() -> dict:
    """Minimal fingerprint dict (fields used by _process)."""
    return {
        'lufs': -14.0, 'crest_db': 12.0, 'bass_mid_ratio': 0.5,
        'sub_bass_pct': 0.05, 'bass_pct': 0.20, 'low_mid_pct': 0.10,
        'mid_pct': 0.20, 'upper_mid_pct': 0.20, 'presence_pct': 0.15,
        'air_pct': 0.10, 'spectral_centroid': 0.5, 'spectral_rolloff': 0.5,
        'spectral_flatness': 0.5, 'tempo_bpm': 120.0,
        'rhythm_stability': 0.5, 'transient_density': 0.5,
        'silence_ratio': 0.0, 'harmonic_ratio': 0.5,
        'pitch_stability': 0.5, 'chroma_energy': 0.5,
        'stereo_width': 0.5, 'phase_correlation': 1.0,
        'dynamic_range_variation': 0.5, 'loudness_variation_std': 0.0,
        'peak_consistency': 0.5,
    }


def _identity_process(audio, *args, **kwargs):
    """Mock _process: return audio unchanged."""
    return audio.copy(), {'stages': [], 'effective_intensity': 0.5}


def _run_pipeline(n_samples: int, crossfade_sec: float, chunk_sec: int = 1) -> int:
    """
    Run master_file() on a synthetic WAV and return the number of output samples.

    Uses identity _process (no DSP) and a fake fingerprint to keep tests fast.
    """
    config = _make_config(crossfade_sec=crossfade_sec, chunk_sec=chunk_sec)
    pipeline = SimpleMasteringPipeline(config=config)

    # fingerprint_service is a read-only @property backed by _fingerprint_service.
    # Set the private attribute directly to avoid touching the lazy-init property.
    mock_fs = MagicMock()
    mock_fs.get_or_compute.return_value = _fake_fingerprint()
    pipeline._fingerprint_service = mock_fs

    with (
        tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as fin,
        tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as fout,
    ):
        input_path = fin.name
        output_path = fout.name

    try:
        _write_sine(input_path, n_samples)

        with patch.object(pipeline, '_process', side_effect=_identity_process):
            pipeline.master_file(input_path, output_path, verbose=False)

        output, _ = sf.read(output_path)
        return len(output)
    finally:
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_zero_crossfade_exact_multiple_chunks_preserves_sample_count():
    """
    With crossfade_sec=0, prev_tail is always empty after the first chunk.
    Before fix: head_len=0 caused np.linspace(0,π/2,0) → empty crossfade →
    write_region had 0 samples for the crossfade section, dropping samples.
    After fix: guard skips crossfade and writes the chunk directly.
    """
    chunk_samples = SR * 1  # 1-second chunks
    n_chunks = 3
    n_samples = chunk_samples * n_chunks  # exact multiple — no remainder

    output_samples = _run_pipeline(
        n_samples=n_samples, crossfade_sec=0.0, chunk_sec=1
    )
    assert output_samples == n_samples, (
        f"Expected {n_samples} samples, got {output_samples}. "
        "Zero-length crossfade guard (fixes #2157) dropped samples."
    )


def test_zero_crossfade_non_multiple_chunks_preserves_sample_count():
    """Same with audio that doesn't divide evenly into chunks."""
    chunk_samples = SR * 1
    # 2.7 chunks worth
    n_samples = int(chunk_samples * 2.7)

    output_samples = _run_pipeline(
        n_samples=n_samples, crossfade_sec=0.0, chunk_sec=1
    )
    assert output_samples == n_samples, (
        f"Expected {n_samples} samples, got {output_samples}."
    )


def test_normal_crossfade_preserves_sample_count():
    """Non-zero crossfade must still produce the correct sample count."""
    chunk_samples = SR * 1
    n_samples = chunk_samples * 3

    # crossfade shorter than chunk — normal operation
    output_samples = _run_pipeline(
        n_samples=n_samples, crossfade_sec=0.1, chunk_sec=1
    )
    assert output_samples == n_samples, (
        f"Normal crossfade changed sample count: expected {n_samples}, "
        f"got {output_samples}."
    )


def test_single_chunk_audio_preserves_sample_count():
    """Audio that fits in exactly one chunk must come out unchanged."""
    n_samples = SR // 2  # 0.5 seconds, well under 1-second chunk

    output_samples = _run_pipeline(
        n_samples=n_samples, crossfade_sec=0.0, chunk_sec=1
    )
    assert output_samples == n_samples


def test_zero_crossfade_two_exact_chunks_preserves_sample_count():
    """Minimal multi-chunk case: exactly 2 chunks with zero crossfade."""
    chunk_samples = SR * 1
    n_samples = chunk_samples * 2

    output_samples = _run_pipeline(
        n_samples=n_samples, crossfade_sec=0.0, chunk_sec=1
    )
    assert output_samples == n_samples, (
        f"Two-chunk zero-crossfade case: expected {n_samples}, "
        f"got {output_samples}."
    )
