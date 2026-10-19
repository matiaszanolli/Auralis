"""End-to-end FFmpeg decode round-trips for every non-MP3 FFMPEG_FORMAT (#5336).

The other five formats (.m4a/.aac/.ogg/.opus/.wma) were only covered by
command-construction tests that mock the subprocess call, so a format-specific
regression in channel handling (-ac), sample-rate handling (-ar), or
codec-specific decode behavior could only surface via a user report. Each test
here encodes a short synthetic stereo sine to the real format with the real
ffmpeg, then decodes it through the real ``load_with_ffmpeg`` and checks the
shape survives.

.mp3 is excluded: it already has real-media end-to-end fixtures
(``tests/input_media/*.mp3``) exercised by the loader suite.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from auralis.io.formats import FFMPEG_FORMAT_NAMES
from auralis.io.loaders.ffmpeg_loader import load_with_ffmpeg

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")

# Extension -> (ffmpeg encoder, source sample rate to encode from). Opus
# always decodes at 48 kHz regardless of the input rate, so encode its source
# at 48 kHz to keep the round-trip rate-preserving; everything else keeps
# 44.1 kHz. libvorbis/libopus may be absent from a minimal ffmpeg build — a
# failed encode skips rather than fails, matching the ALAC pattern in
# test_ffmpeg_bit_depth_preservation_5317.py.
_ENCODERS = {
    '.m4a': ('aac', 44100),
    '.aac': ('aac', 44100),
    '.ogg': ('libvorbis', 44100),
    '.opus': ('libopus', 48000),
    '.wma': ('wmav2', 44100),
}

_TONE_HZ = 997.0
_AMPLITUDE = 0.5
_SOURCE_SECONDS = 1.0


def _encode_source(tmp_path: Path, ext: str) -> tuple[Path, int, int]:
    """Write a 1 s stereo sine WAV and encode it to ``ext`` with real ffmpeg.

    Returns (encoded path, source frame count, source sample rate).
    """
    encoder, sr = _ENCODERS[ext]
    n = int(sr * _SOURCE_SECONDS)
    t = np.arange(n) / sr
    tone = (_AMPLITUDE * np.sin(2 * np.pi * _TONE_HZ * t)).astype(np.float32)
    stereo = np.stack([tone, tone], axis=1)

    src_wav = tmp_path / "src.wav"
    sf.write(str(src_wav), stereo, sr, subtype="PCM_16")

    encoded = tmp_path / f"src{ext}"
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", str(src_wav), "-c:a", encoder, str(encoded), "-y"],
        capture_output=True, timeout=60,
    )
    if result.returncode != 0 or not encoded.exists() or encoded.stat().st_size == 0:
        pytest.skip(f"{encoder} encode unavailable in this ffmpeg build: {result.stderr!r}")
    return encoded, n, sr


@needs_ffmpeg
class TestFFmpegFormatRoundTrips:
    @pytest.mark.parametrize("ext", [e for e in FFMPEG_FORMAT_NAMES if e != '.mp3'])
    def test_roundtrip_preserves_sample_rate_channels_and_length(self, tmp_path, ext):
        encoded, src_frames, src_sr = _encode_source(tmp_path, ext)

        audio, decoded_sr = load_with_ffmpeg(encoded, str(tmp_path))

        # -ar must preserve the file's native rate (#2495): a hardcoded rate
        # silently resampled 48 kHz sources to the wrong pitch.
        assert decoded_sr == src_sr
        # Stereo in, stereo out (downmix only fires above 2 channels, #4611).
        assert audio.ndim == 2
        assert audio.shape[1] == 2
        # Lossy codecs add encoder priming/padding sized in codec frames
        # (AAC 1024, Opus 960, WMA2's block), so the decoded length may
        # differ from the source by a couple of frames — but a broken
        # decode (wrong -t, half-decoded stream, misparsed container)
        # misses by a large fraction of the file.
        assert abs(len(audio) - src_frames) <= 8192
        # A real decode of a real tone: finite samples at a sane level,
        # not silence or garbage.
        assert np.isfinite(audio).all()
        rms = float(np.sqrt(np.mean(audio.mean(axis=1) ** 2)))
        assert rms > 0.1, f"decoded audio is not the encoded sine (rms={rms:.4f})"
