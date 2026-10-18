"""
Regression: FFmpeg pre-transcode goes through saver.save() (#5532)

``SimpleMasteringPipeline._master_file_impl`` decoded FFmpeg-only formats
(mp3/m4a/aac/…) and re-encoded to a temp WAV with a bare ``sf.write`` —
bypassing ``auralis.io.saver.save()``'s NaN/Inf repair and [-1, 1] clip.
``load_with_ffmpeg`` has no finiteness guard, so a corrupt decode produced
non-finite samples that PCM_24 quantization turned into finite garbage —
which the downstream fail-fast finite check (mastering_process_chunk) can
never catch, because the value is no longer NaN.

The fix routes the temp-WAV write through ``saver.save()``: non-finite
samples become silence before they reach the file. These tests use the real
pipeline with a mocked ``_process`` (identity) and a patched
``load_with_ffmpeg``, mirroring ``test_master_file_mono_input.py``.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.simple_mastering import SimpleMasteringPipeline

SR = 44100


def _make_config() -> SimpleMasteringConfig:
    config = SimpleMasteringConfig()
    config.CROSSFADE_DURATION_SEC = 0.0
    config.CHUNK_DURATION_SEC = 1
    return config


def _make_pipeline() -> SimpleMasteringPipeline:
    pipeline = SimpleMasteringPipeline(config=_make_config())
    mock_fs = MagicMock()
    mock_fs.get_or_compute.return_value = {
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
    pipeline._fingerprint_service = mock_fs
    return pipeline


def _identity_process(audio: np.ndarray, *args, **kwargs):
    return audio.copy(), {'stages': [], 'effective_intensity': 0.5}


def _master_ffmpeg_input(raw_buffer: np.ndarray) -> np.ndarray:
    """Master through the FFmpeg branch (a .mp3 input with a patched decoder)
    and return the decoded output."""
    pipeline = _make_pipeline()
    with (
        tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as fin,
        tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as fout,
    ):
        input_path = fin.name
        output_path = fout.name
    try:
        with (
            patch('auralis.io.loaders.load_with_ffmpeg', return_value=(raw_buffer, SR)),
            patch.object(pipeline, '_process', side_effect=_identity_process),
        ):
            pipeline.master_file(input_path, output_path, verbose=False)

        output, _ = sf.read(output_path, dtype='float32')
        return output
    finally:
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)


def test_non_finite_decode_is_repaired_to_silence():
    """NaN/Inf in the FFmpeg decode must reach the DSP pipeline as finite
    audio — repaired to silence by saver.save(), not quantized into
    arbitrary PCM_24 garbage."""
    raw = (0.2 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)
    nan_positions = [10, 5000, 40_000]
    raw[nan_positions] = np.nan
    raw[30_000] = np.inf

    output = _master_ffmpeg_input(raw)  # must not raise

    assert output.size > 0
    assert np.all(np.isfinite(output)), "non-finite sample survived the pre-transcode"
    assert np.all(np.abs(output) <= 1.0), "out-of-range sample survived the pre-transcode"
    # NaN/Inf positions were in the LEFT channel of an interleaved stereo
    # buffer (mono expanded to stereo): they must now be exact silence.
    assert np.all(output[nan_positions, 0] == 0.0)
    assert np.isfinite(output[30_000, 0]) and output[30_000, 0] == 0.0


def test_out_of_range_decode_is_clipped():
    """Out-of-range samples from the decoder are clamped to [-1, 1] at the
    pre-transcode boundary (saver.save's deterministic clip)."""
    raw = (0.1 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)
    raw[1000] = 7.5
    raw[2000] = -7.5

    output = _master_ffmpeg_input(raw)

    assert np.all(np.abs(output) <= 1.0)
