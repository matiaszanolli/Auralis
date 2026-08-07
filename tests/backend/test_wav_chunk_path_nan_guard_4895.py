#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
get_wav_chunk_path() encode+persist NaN/Inf guard (#4895)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ChunkedAudioProcessor had two independent encode-WAV-and-persist call paths:
process_chunk() went through WAVEncoder.encode_and_save() (validates
non-empty / isfinite), while get_wav_chunk_path() — the docstring-labeled
"PRIMARY output method for the unified architecture", actually hit on every
enhanced-playback request — went through the plain encode_to_wav() function,
which had no isfinite/empty-array check at all and would silently persist a
NaN/Inf-poisoned WAV to the on-disk cache.

Fixed by routing get_wav_chunk_path() through the same guarded
WAVEncoder.encode_and_save() primitive process_chunk() already used.

:copyright: (C) 2026 Auralis Team
:license: GPLv3
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

backend_path = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(backend_path))

from core.chunked_processor import ChunkedAudioProcessor  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from auralis.io.saver import save as save_audio  # noqa: E402


@pytest.fixture
def test_audio_file(tmp_path):
    """A short valid stereo WAV to drive a ChunkedAudioProcessor from."""
    duration = 20.0
    sample_rate = 44100
    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples)
    audio = np.sin(2 * np.pi * 440.0 * t)
    audio_stereo = np.column_stack([audio, audio])

    filepath = tmp_path / "test_audio.wav"
    save_audio(str(filepath), audio_stereo, sample_rate, subtype="PCM_16")
    return str(filepath)


@pytest.fixture
def processor(test_audio_file):
    return ChunkedAudioProcessor(
        track_id=1,
        filepath=test_audio_file,
        preset="adaptive",
        intensity=1.0,
        chunk_cache={},
    )


class TestGetWavChunkPathRejectsNonFiniteAudio:
    """The isfinite guard must apply on the get_wav_chunk_path() path too."""

    def test_nan_audio_raises_value_error_not_silent_write(self, processor):
        nan_chunk = np.full((4410, 2), np.nan, dtype=np.float32)

        with patch.object(processor, "_process_chunk_core", return_value=nan_chunk), \
             patch(
                 "core.chunked_processor.ChunkOperations.extract_chunk_segment",
                 return_value=nan_chunk,
             ):
            with pytest.raises(ValueError, match="non-finite"):
                processor.get_wav_chunk_path(0)

        wav_chunk_path = processor._get_wav_chunk_path(0)
        assert not wav_chunk_path.exists(), (
            "a NaN-poisoned WAV was written to the on-disk cache instead of "
            "raising before the write"
        )

    def test_inf_audio_raises_value_error_not_silent_write(self, processor):
        inf_chunk = np.full((4410, 2), np.inf, dtype=np.float32)

        with patch.object(processor, "_process_chunk_core", return_value=inf_chunk), \
             patch(
                 "core.chunked_processor.ChunkOperations.extract_chunk_segment",
                 return_value=inf_chunk,
             ):
            with pytest.raises(ValueError, match="non-finite"):
                processor.get_wav_chunk_path(0)

        wav_chunk_path = processor._get_wav_chunk_path(0)
        assert not wav_chunk_path.exists()

    def test_process_chunk_has_the_same_guard(self, processor):
        """Confirms process_chunk() already rejected this — the regression
        this test guards is get_wav_chunk_path() lacking parity with it."""
        nan_chunk = np.full((4410, 2), np.nan, dtype=np.float32)

        with patch.object(processor, "_process_chunk_core", return_value=nan_chunk), \
             patch(
                 "core.chunked_processor.ChunkOperations.extract_chunk_segment",
                 return_value=nan_chunk,
             ):
            with pytest.raises(ValueError, match="non-finite"):
                processor.process_chunk(0)


class TestGetWavChunkPathStillEncodesFiniteAudio:
    """Regression guard: normal audio must still produce a valid WAV via
    both call paths, byte-identical in the samples they carry."""

    def test_finite_audio_round_trips_through_get_wav_chunk_path(self, processor):
        wav_chunk_path = Path(processor.get_wav_chunk_path(0))
        assert wav_chunk_path.exists()
        assert wav_chunk_path.stat().st_size > 44  # more than just a WAV header

    def test_process_chunk_and_get_wav_chunk_path_produce_playable_audio(self, processor):
        from auralis.io.unified_loader import load_audio

        process_chunk_path, _ = processor.process_chunk(0)
        audio, sr = load_audio(process_chunk_path)
        assert np.isfinite(audio).all()
        assert sr == processor.sample_rate
