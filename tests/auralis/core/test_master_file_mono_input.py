"""
Regression: mono input file must master to a valid stereo output (#4494)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`mastering_chunk_loop.process_chunks` opened the output sink with
``channels = min(channels, 2)`` — 1 for a mono file — but every processing
path expands mono to stereo before writing, so a ``(frames, 2)`` array was
always written to a 1-channel sink, raising::

    ValueError: Invalid shape (..., 2) (Expected 1 channels, got 2)

on the first write for any mono source (data loss for that job). The fix opens
the sink with 2 channels unconditionally.

These tests use the real ``SimpleMasteringPipeline`` with a mocked ``_process``
(identity transform) so they exercise the chunk loop without touching the DSP,
mirroring ``test_short_stereo_transpose.py``.
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


def _master_mono(mono_data: np.ndarray) -> np.ndarray:
    """Write *mono_data* (1-D) as a true 1-channel WAV, master it, and return
    the output audio read back from the written file."""
    pipeline = _make_pipeline()
    with (
        tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as fin,
        tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as fout,
    ):
        input_path = fin.name
        output_path = fout.name
    try:
        sf.write(input_path, mono_data, SR)
        # Sanity: the input really is 1-channel.
        assert sf.info(input_path).channels == 1

        with patch.object(pipeline, '_process', side_effect=_identity_process):
            pipeline.master_file(input_path, output_path, verbose=False)

        output, _ = sf.read(output_path, dtype='float32')
        return output
    finally:
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)


class TestMasterFileMonoInput:
    def test_mono_input_masters_without_exception(self):
        """A true mono file must master without raising (was ValueError)."""
        mono = (0.2 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)
        output = _master_mono(mono)  # must not raise
        assert output.size > 0

    def test_mono_output_is_stereo(self):
        """Output opens as a 2-channel file (mono is expanded to stereo)."""
        mono = (0.2 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)
        output = _master_mono(mono)
        assert output.ndim == 2 and output.shape[1] == 2, (
            f"Expected stereo output, got shape {output.shape}"
        )

    def test_mono_sample_count_preserved(self):
        """Output frame count equals input frame count."""
        n = SR + 1234  # spans more than one chunk boundary
        mono = (0.2 * np.sin(2 * np.pi * 220 * np.arange(n) / SR)).astype(np.float32)
        output = _master_mono(mono)
        assert output.shape[0] == n, (
            f"Sample count changed: input {n} -> output {output.shape[0]}"
        )
