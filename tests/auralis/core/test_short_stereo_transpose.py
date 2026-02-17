"""
Tests for transpose heuristic fix on very short stereo audio (issue #2292)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The old heuristic ``chunk.shape[0] > chunk.shape[1]`` fails for square
arrays (e.g. shape ``(2, 2)`` = 2-sample stereo), because ``2 > 2`` is
``False`` so the transpose to ``(channels, samples)`` is skipped.  The
result is that L/R channels are silently swapped inside ``_process()``,
and the write-back transpose is also skipped, corrupting the output.

Acceptance criteria:
 - 2-sample stereo audio passes through the pipeline without corruption
 - 1-sample stereo audio (shape (1, 2)) passes through correctly
 - Output channel data matches input (identity _process mock)
 - Existing sample-count invariant still holds for all short-audio cases

All tests use the real SimpleMasteringPipeline with a mocked _process
(identity transform) so they run quickly without touching the DSP code.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.simple_mastering import SimpleMasteringPipeline


# ---------------------------------------------------------------------------
# Helpers (mirrors the pattern from test_crossfade_zero_length_boundary.py)
# ---------------------------------------------------------------------------

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
    """Return audio unchanged — lets us verify channel layout is preserved."""
    return audio.copy(), {'stages': [], 'effective_intensity': 0.5}


def _run_on_audio(stereo_data: np.ndarray) -> np.ndarray:
    """
    Run master_file() on *stereo_data* (samples, 2) and return the output
    audio array read back from the written WAV file.
    """
    pipeline = _make_pipeline()

    with (
        tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as fin,
        tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as fout,
    ):
        input_path = fin.name
        output_path = fout.name

    try:
        sf.write(input_path, stereo_data, SR)

        with patch.object(pipeline, '_process', side_effect=_identity_process):
            pipeline.master_file(input_path, output_path, verbose=False)

        output, _ = sf.read(output_path, dtype='float32')
        return output
    finally:
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestShortStereoTranspose:
    """Verify transpose logic for edge-case very short stereo audio."""

    def test_two_sample_stereo_sample_count_preserved(self):
        """2-sample stereo (shape (2, 2)) must produce 2 output samples.

        Before fix: shape[0] > shape[1] → 2 > 2 → False → no transpose →
        _process receives (samples, channels) interpreted as (channels, samples)
        → channels swapped and write_region also not transposed back.
        """
        data = np.array([[0.1, -0.1], [0.2, -0.2]], dtype=np.float32)
        output = _run_on_audio(data)
        assert output.shape[0] == 2, (
            f"Expected 2 output samples, got {output.shape[0]} "
            "(transpose heuristic bug #2292 dropped or duplicated samples)"
        )

    def test_two_sample_stereo_channel_data_preserved(self):
        """With identity _process, output channel values must match input.

        The old bug swapped L/R channels inside _process (even without
        changing the sample count) because (samples, channels) was passed
        as if it were (channels, samples).
        """
        # Use distinct per-channel values to detect channel swapping.
        left = np.array([0.5, 0.6], dtype=np.float32)
        right = np.array([-0.5, -0.6], dtype=np.float32)
        data = np.column_stack([left, right])  # shape (2, 2)

        output = _run_on_audio(data)

        assert output.shape == (2, 2), f"Unexpected output shape: {output.shape}"
        # Left channel (col 0) must stay positive; right channel (col 1) negative.
        assert np.all(output[:, 0] > 0), (
            "Left channel corrupted — channels were likely swapped (issue #2292)"
        )
        assert np.all(output[:, 1] < 0), (
            "Right channel corrupted — channels were likely swapped (issue #2292)"
        )

    def test_one_sample_stereo_sample_count_preserved(self):
        """1-sample stereo (shape (1, 2)) must produce 1 output sample.

        shape[0] > shape[1] → 1 > 2 → False → same bug as 2-sample case.
        """
        data = np.array([[0.3, -0.3]], dtype=np.float32)  # shape (1, 2)
        output = _run_on_audio(data)
        assert output.shape[0] == 1, (
            f"Expected 1 output sample, got {output.shape[0]} (issue #2292)"
        )

    def test_one_sample_stereo_channel_data_preserved(self):
        """1-sample stereo channel values must not be swapped."""
        data = np.array([[0.7, -0.7]], dtype=np.float32)
        output = _run_on_audio(data)
        assert output.shape == (1, 2), f"Unexpected output shape: {output.shape}"
        assert output[0, 0] > 0, "Left channel corrupted (issue #2292)"
        assert output[0, 1] < 0, "Right channel corrupted (issue #2292)"

    def test_normal_length_stereo_unaffected(self):
        """Ensure the fix does not break normal-length audio (regression guard).

        For n_samples >> 2 the old heuristic was always correct, so this
        verifies the unconditional transpose is equivalent for normal audio.
        """
        n_samples = SR  # 1 second
        t = np.linspace(0, 1, n_samples, endpoint=False, dtype=np.float32)
        left = 0.3 * np.sin(2 * np.pi * 440 * t)
        right = 0.3 * np.sin(2 * np.pi * 880 * t)
        data = np.column_stack([left, right])

        output = _run_on_audio(data)
        assert output.shape[0] == n_samples, (
            f"Normal audio sample count changed: expected {n_samples}, "
            f"got {output.shape[0]}"
        )
        assert output.shape[1] == 2, "Expected stereo output"
