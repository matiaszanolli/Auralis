"""
Regression tests for self-describing WAV chunk overlap metadata (#3872)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The per-chunk WAV bytes previously carried no in-band overlap awareness, so the
frontend had to trust seconds-based metadata and arrival order to trim overlap.
These tests cover:

- ``read_wav_frame_info()`` recovers the exact frame count + sample rate from
  encoded WAV bytes (authoritative regardless of cache tier).
- ``_compute_chunk_sample_layout()`` derives playable/overlap/start-offset
  sample counts correctly for no-overlap, overlapping, and short-final chunks,
  and degrades gracefully on unparseable bytes.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from encoding.wav_encoder import WAVEncoderError, encode_to_wav, read_wav_frame_info
from routers.wav_streaming import _compute_chunk_sample_layout


def _make_wav(n_frames: int, sample_rate: int = 44100, channels: int = 2) -> bytes:
    """Encode `n_frames` of silence to WAV bytes."""
    audio = np.zeros((n_frames, channels), dtype=np.float32)
    return encode_to_wav(audio, sample_rate)


class TestReadWavFrameInfo:
    """read_wav_frame_info() round-trips frame count and sample rate."""

    def test_roundtrip_frame_count_and_rate(self):
        wav = _make_wav(n_frames=12345, sample_rate=48000)
        n_frames, sr = read_wav_frame_info(wav)
        assert n_frames == 12345
        assert sr == 48000

    def test_default_sample_rate(self):
        wav = _make_wav(n_frames=44100, sample_rate=44100)
        n_frames, sr = read_wav_frame_info(wav)
        assert n_frames == 44100
        assert sr == 44100

    def test_invalid_bytes_raise(self):
        with pytest.raises(WAVEncoderError):
            read_wav_frame_info(b"not a wav file")


class TestComputeChunkSampleLayout:
    """_compute_chunk_sample_layout() derives correct overlap layout."""

    SR = 44100

    def test_no_overlap_config_full_chunk_playable(self):
        """duration == interval → no overlap, whole chunk playable."""
        wav = _make_wav(n_frames=10 * self.SR, sample_rate=self.SR)
        layout = _compute_chunk_sample_layout(wav, chunk_idx=2, chunk_duration=10, chunk_interval=10)
        assert layout is not None
        assert layout["sample_rate"] == self.SR
        assert layout["total_samples"] == 10 * self.SR
        assert layout["overlap_samples"] == 0
        assert layout["playable_samples"] == 10 * self.SR
        # Absolute placement: chunk 2 starts at 2 * interval seconds.
        assert layout["start_sample_offset"] == 2 * 10 * self.SR

    def test_overlap_config_full_chunk(self):
        """15s chunk / 10s interval → 5s trailing overlap, 10s playable."""
        wav = _make_wav(n_frames=15 * self.SR, sample_rate=self.SR)
        layout = _compute_chunk_sample_layout(wav, chunk_idx=1, chunk_duration=15, chunk_interval=10)
        assert layout is not None
        assert layout["total_samples"] == 15 * self.SR
        assert layout["overlap_samples"] == 5 * self.SR
        assert layout["playable_samples"] == 10 * self.SR
        assert layout["start_sample_offset"] == 1 * 10 * self.SR

    def test_short_final_chunk_no_overlap(self):
        """A short final chunk (< interval) carries no trailing overlap."""
        short_frames = 3 * self.SR  # 3s, shorter than the 10s interval
        wav = _make_wav(n_frames=short_frames, sample_rate=self.SR)
        layout = _compute_chunk_sample_layout(wav, chunk_idx=5, chunk_duration=15, chunk_interval=10)
        assert layout is not None
        assert layout["total_samples"] == short_frames
        assert layout["overlap_samples"] == 0
        assert layout["playable_samples"] == short_frames
        assert layout["start_sample_offset"] == 5 * 10 * self.SR

    def test_chunk_exactly_interval_length_no_overlap(self):
        """A chunk exactly interval-length is fully playable (boundary)."""
        wav = _make_wav(n_frames=10 * self.SR, sample_rate=self.SR)
        layout = _compute_chunk_sample_layout(wav, chunk_idx=0, chunk_duration=15, chunk_interval=10)
        assert layout is not None
        assert layout["overlap_samples"] == 0
        assert layout["playable_samples"] == 10 * self.SR

    def test_unparseable_bytes_return_none(self):
        """Parse failure degrades gracefully (headers omitted, request unaffected)."""
        layout = _compute_chunk_sample_layout(b"garbage", chunk_idx=0, chunk_duration=10, chunk_interval=10)
        assert layout is None

    def test_playable_plus_overlap_equals_total(self):
        """Invariant: playable + overlap == total for any full chunk."""
        wav = _make_wav(n_frames=15 * self.SR, sample_rate=self.SR)
        layout = _compute_chunk_sample_layout(wav, chunk_idx=3, chunk_duration=15, chunk_interval=10)
        assert layout is not None
        assert layout["playable_samples"] + layout["overlap_samples"] == layout["total_samples"]
