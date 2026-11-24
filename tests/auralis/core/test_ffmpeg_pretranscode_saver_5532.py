"""
Regression: the FFmpeg pre-transcode repairs non-finite samples and keeps overshoot (#5532, #5739, #6360)

``SimpleMasteringPipeline._master_file_impl`` decoded FFmpeg-only formats
(mp3/m4a/aac/…) and re-encoded to a temp WAV with a bare ``sf.write`` —
bypassing ``auralis.io.saver.save()``'s NaN/Inf repair and [-1, 1] clip.
``load_with_ffmpeg`` has no finiteness guard, so a corrupt decode produced
non-finite samples that PCM_24 quantization turned into finite garbage —
which the downstream fail-fast finite check (mastering_process_chunk) can
never catch, because the value is no longer NaN.

The fix routed the temp-WAV write through ``saver.save()``: non-finite
samples became silence before they reached the file. Since #5739 the decode is
streamed to a float32 WAV that is never held in RAM, so the same guarantee comes
from ``auralis.io.wav_sanitize`` run over that file. These tests use the real
pipeline with a mocked ``_process`` (identity) and a patched ``decode_to_wav``
that leaves a corrupt float WAV, mirroring ``test_master_file_mono_input.py``.
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
        def fake_decode(path, temp_folder, cancel_event=None):
            wav = Path(temp_folder) / 'decoded.wav'
            sf.write(str(wav), np.column_stack([raw_buffer, raw_buffer]), SR, subtype='FLOAT')
            return wav

        with (
            patch('auralis.io.loaders.decode_to_wav', side_effect=fake_decode),
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


def test_decoder_overshoot_is_kept_and_only_non_finite_samples_are_repaired(tmp_path):
    """#6360: codec overshoot past full scale reaches the engine, as it does from load_audio() and
    as saver.save() keeps it for a float subtype (#6316). Clipping it here hard-clipped AAC/MP3
    peaks on the FFmpeg-decode route only. A file with only overshoot is not rewritten."""
    from auralis.io.wav_sanitize import sanitize_wav_in_place

    overshoot = (0.1 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)
    overshoot[1000], overshoot[2000] = 1.48, -1.16
    clean = tmp_path / 'overshoot.wav'
    sf.write(str(clean), overshoot, SR, format='WAV', subtype='FLOAT')

    assert sanitize_wav_in_place(clean, block_frames=4096) is False
    np.testing.assert_array_equal(sf.read(str(clean), dtype='float32')[0], overshoot)

    corrupt = overshoot.copy()
    corrupt[3000] = np.nan
    bad = tmp_path / 'corrupt.wav'
    sf.write(str(bad), corrupt, SR, format='WAV', subtype='FLOAT')

    assert sanitize_wav_in_place(bad, block_frames=4096) is True
    repaired = sf.read(str(bad), dtype='float32')[0]
    assert repaired[3000] == 0.0
    assert repaired[1000] == np.float32(1.48) and repaired[2000] == np.float32(-1.16)


def test_a_real_mp3_is_mastered_from_the_streamed_decode(tmp_path):
    """End to end with a real FFmpeg decode (#5739): same length out as in, nothing left in /tmp."""
    import shutil
    import subprocess

    import pytest

    if shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None:
        pytest.skip('ffmpeg not installed')

    tone = (0.3 * np.sin(2 * np.pi * 330 * np.arange(3 * SR) / SR)).astype(np.float32)
    src_wav = tmp_path / 'src.wav'
    sf.write(str(src_wav), np.column_stack([tone, tone]), SR)
    src = tmp_path / 'song.mp3'
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-i', str(src_wav), str(src)], check=True)
    expected_frames = sf.info(str(src_wav)).frames
    out = tmp_path / 'out.wav'

    pipeline = _make_pipeline()
    with patch.object(pipeline, '_process', side_effect=_identity_process):
        pipeline.master_file(str(src), str(out), verbose=False)

    info = sf.info(str(out))
    assert info.samplerate == SR
    assert abs(info.frames - expected_frames) < 0.1 * SR  # mp3 pads/trims a few ms
    assert not [p for p in tmp_path.iterdir() if p.name.endswith('.repaired')]
