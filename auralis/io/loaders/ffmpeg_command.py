"""
FFmpeg conversion argv and decode validation (split from ffmpeg_loader.py,
#5835): pure helpers with no subprocess or filesystem access.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path

import numpy as np

from ...utils.logging import Code, ModuleError, debug, warning
from ..processing import decoded_channel_count
from .ffmpeg_probe import _PROTOCOL_WHITELIST_ARGS


def build_ffmpeg_cmd(
    file_path_str: str,
    temp_wav: Path,
    source_sample_rate: int,
    source_channels: int,
    offset: float | None,
    duration: float | None,
) -> list[str]:
    """The ffmpeg argv converting the input to a float32 temp WAV."""
    # #3672: `-ac 2` lets FFmpeg apply its proper surround downmix matrix (center
    # at -3 dB into L+R, surrounds distributed); `-ac {source_channels}` plus a
    # `[:, :2]` truncation in soundfile_loader silently dropped the center channel.
    #
    # #4611/#4597: gated on decoded_channel_count() (> 2 sources only); applying it
    # to mono *up*-mixed it into fake stereo, so get_audio_info() (true ffprobe
    # count) and load_audio() (a 2-D array) disagreed. soundfile_loader likewise
    # downmixes only when `shape[1] > 2`.
    needs_downmix = decoded_channel_count(source_channels) != source_channels
    # -nostdin: the child must never read the backend's terminal; -hide_banner and
    # -loglevel error keep stderr to the failure reason (#5731).
    ffmpeg_cmd = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', *_PROTOCOL_WHITELIST_ARGS]
    # -ss BEFORE -i is input seeking: ffmpeg jumps to the offset instead of
    # decoding and discarding everything ahead of it (#5110).
    if offset is not None and offset > 0:
        ffmpeg_cmd += ['-ss', f'{offset:.6f}']
    ffmpeg_cmd += [
        '-i', file_path_str,
        # 32-bit float PCM, not 16-bit (#5317): a source with more than
        # 16 bits of real precision (24-bit ALAC-in-M4A, WMA Lossless)
        # was being truncated to ~96 dB of dynamic range before any DSP
        # or fingerprinting ran. load_with_soundfile() reads the temp WAV
        # back as float32 regardless of its sample format, so this loses
        # nothing and needs no bits_per_raw_sample probe.
        '-acodec', 'pcm_f32le',
        '-ar', str(source_sample_rate),    # Preserve native sample rate
    ]
    if duration is not None and duration > 0:
        ffmpeg_cmd += ['-t', f'{duration:.6f}']
    if needs_downmix:
        ffmpeg_cmd += ['-ac', '2']         # Surround → stereo (#3672)
    ffmpeg_cmd += [
        '-y',                              # Overwrite output
        str(temp_wav)
    ]
    if offset is not None or duration is not None:
        debug(
            f"FFmpeg: bounded decode offset={offset}s duration={duration}s "
            f"(instead of the full file)"
        )
    if needs_downmix:
        debug(f"FFmpeg: converting at {source_sample_rate} Hz, "
              f"downmixing {source_channels} → 2 ch")
    else:
        debug(f"FFmpeg: converting at {source_sample_rate} Hz, "
              f"preserving {source_channels} ch")
    return ffmpeg_cmd


def check_truncation(
    audio_data: np.ndarray,
    sample_rate: int,
    expected_duration: float | None,
    offset: float | None,
    duration: float | None,
) -> None:
    """Validate the decoded length against the source metadata.

    #5110: with a bounded decode the output is deliberately shorter than the
    source, so comparing against the *file's* duration would flag every
    windowed read as severely truncated. Compare against the span that was
    actually requested instead — the check still catches a decode that
    returned far less than asked for, which is what it is for.
    """
    effective_expected = expected_duration
    if effective_expected is not None and (offset is not None or duration is not None):
        remaining = max(0.0, effective_expected - (offset or 0.0))
        effective_expected = min(duration, remaining) if duration else remaining

    if effective_expected is not None and effective_expected > 0:
        actual_duration = len(audio_data) / sample_rate
        expected_duration = effective_expected
        duration_percentage = (actual_duration / expected_duration) * 100

        if duration_percentage < 10:
            # Severely truncated - raise error
            raise ModuleError(
                f"{Code.ERROR_TRUNCATED_FILE}: File is severely truncated "
                f"({duration_percentage:.1f}% complete, expected {expected_duration:.2f}s, got {actual_duration:.2f}s)"
            )
        elif duration_percentage < 90:
            # Moderately truncated - log warning
            warning(
                f"{Code.WARNING_TRUNCATED_FILE}: File appears truncated "
                f"({duration_percentage:.1f}% complete, expected {expected_duration:.2f}s, got {actual_duration:.2f}s)"
            )
