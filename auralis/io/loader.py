"""
Auralis Audio Loader
~~~~~~~~~~~~~~~~~~~~

Audio file loading and validation

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""


from pathlib import Path

import numpy as np
import soundfile as sf

from ..utils.logging import ModuleError, debug, info, warning
from .formats import FFMPEG_FORMATS
from .loaders import load_with_ffmpeg
from .processing import downmix_to_stereo, requires_layout_aware_downmix


# Maximum audio duration (seconds) that can be loaded into RAM.
# 2 hours of stereo float32 at 96 kHz ≈ 5.3 GB — a safe upper bound.
#
# #3758: overridable via the `AURALIS_MAX_DURATION_SECONDS` environment
# variable so users with legitimate long-form content (3-hour live
# concert masters, podcast archive, etc.) can opt in without patching
# the source. The default stays at 7200 (2 h) which covers the
# overwhelming majority of music files. Setting a higher value is the
# user's explicit acknowledgement that they have the RAM headroom.
import os as _os
try:
    MAX_DURATION_SECONDS = int(_os.environ.get(
        "AURALIS_MAX_DURATION_SECONDS", "7200"
    ))
except ValueError:
    MAX_DURATION_SECONDS = 7200

# Ceiling on the ESTIMATED decoded size, in bytes.
#
# The duration cap above is justified in its own comment as "2 hours of stereo
# float32 at 96 kHz ≈ 5.3 GB" — but nothing ever checked sample rate or channel
# count, so that arithmetic was an assumption about the input, not a property of
# it (#4875). The same 7200 s at 192 kHz stereo decodes to ~10.3 GiB, and at
# 192 kHz 5.1 to ~31 GiB. Duration alone cannot bound memory.
#
# 6 GiB is chosen to sit just above the profile the duration cap was tuned for
# (2 h / 96 kHz / stereo ≈ 5.15 GiB), so nothing that was previously accepted
# and genuinely safe starts failing, while the high-rate/multichannel cases the
# duration cap silently admitted are rejected before the decode.
#
# Overridable via AURALIS_MAX_DECODED_BYTES, mirroring
# AURALIS_MAX_DURATION_SECONDS (#3758) — an operator who raises one and not the
# other would otherwise hit a new hardcoded wall with no way past it.
try:
    MAX_DECODED_BYTES = int(_os.environ.get(
        "AURALIS_MAX_DECODED_BYTES", str(6 * 1024 ** 3)
    ))
except ValueError:
    MAX_DECODED_BYTES = 6 * 1024 ** 3
del _os

# float32 — soundfile_loader reads with an explicit float32 dtype (#3748) and
# the FFmpeg path lands in the same representation.
_BYTES_PER_SAMPLE = 4


def estimated_decoded_bytes(
    duration_seconds: float, sample_rate: int, channels: int
) -> int:
    """Peak bytes a decode of this shape will occupy, before downstream copies."""
    return int(
        max(duration_seconds, 0.0)
        * max(sample_rate, 0)
        * max(channels, 1)
        * _BYTES_PER_SAMPLE
    )


def oversize_decode_detail(
    duration_seconds: float, sample_rate: int, channels: int
) -> str | None:
    """Message describing the overrun, or None when the decode is within budget.

    Returns the detail rather than raising so each call site can keep its own
    ``Code.*`` prefix — the soundfile and FFmpeg paths report different error
    codes for the same condition, and collapsing them would change the error
    taxonomy callers already match on.
    """
    estimated = estimated_decoded_bytes(duration_seconds, sample_rate, channels)
    if estimated <= MAX_DECODED_BYTES:
        return None
    gib = 1024 ** 3
    return (
        f"Audio file exceeds maximum decoded size "
        f"({estimated / gib:.1f} GiB > {MAX_DECODED_BYTES / gib:.1f} GiB; "
        f"{duration_seconds:.0f}s x {sample_rate} Hz x {channels}ch x "
        f"{_BYTES_PER_SAMPLE}B)"
    )


def load(file_path: str, file_type: str = "audio") -> tuple[np.ndarray, int]:
    """
    Load an audio file

    Args:
        file_path: Path to the audio file
        file_type: Type of file being loaded ("target", "reference", or "audio")

    Returns:
        tuple: (audio_data, sample_rate)

    Raises:
        RuntimeError: If the file exceeds MAX_DURATION_SECONDS, or if its
            estimated decoded size exceeds MAX_DECODED_BYTES (#4875, #5104)
    """
    debug(f"Loading {file_type} file: {file_path}")

    try:
        # Route FFmpeg-required formats (M4A, AAC, WMA, OPUS, MP3, OGG)
        # through FFmpeg; use SoundFile for natively supported formats
        file_ext = Path(file_path).suffix.lower()
        if file_ext in FFMPEG_FORMATS:
            audio_data, sample_rate = load_with_ffmpeg(Path(file_path))
            # Guard FFmpeg path: check duration after decode (#3300)
            duration = len(audio_data) / max(sample_rate, 1)
            if duration > MAX_DURATION_SECONDS:
                raise RuntimeError(
                    f"Audio file exceeds maximum duration "
                    f"({duration:.0f}s > {MAX_DURATION_SECONDS}s): {file_path}"
                )
        else:
            file_info = sf.info(file_path)
            # Guard against OOM: reject files that would exhaust RAM (#3300)
            if file_info.duration > MAX_DURATION_SECONDS:
                raise RuntimeError(
                    f"Audio file exceeds maximum duration "
                    f"({file_info.duration:.0f}s > {MAX_DURATION_SECONDS}s): {file_path}"
                )
            # Duration alone does not bound memory (#4875). #4875 applied the
            # byte budget to soundfile_loader/ffmpeg_loader/unified_loader but
            # not to this function — the loader auralis/player/ imports directly
            # — so a 192 kHz stereo WAV under the duration cap was accepted here
            # and rejected by every other decode path (#5104). sf.info already
            # carries samplerate and channels, so the check is free.
            detail = oversize_decode_detail(
                file_info.duration, file_info.samplerate, file_info.channels
            )
            if detail:
                raise RuntimeError(f"{detail}: {file_path}")
            if requires_layout_aware_downmix(file_info.channels):
                warning(
                    f"Routing {file_info.channels}-channel audio through FFmpeg; "
                    "native downmix only supports canonical 5.1/7.1 channel ordering"
                )
                audio_data, sample_rate = load_with_ffmpeg(Path(file_path))
            else:
                audio_data, sample_rate = sf.read(
                    file_path, dtype=np.float32, always_2d=True
                )
                if len(audio_data) < file_info.frames:
                    raise RuntimeError(
                        f"Truncated audio file '{file_path}': "
                        f"expected {file_info.frames} frames, got {len(audio_data)}"
                    )

        # Ensure float32
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # Ensure stereo (2D)
        if audio_data.ndim == 1:
            # Mono 1D → stereo 2D
            audio_data = np.column_stack([audio_data, audio_data])
        elif audio_data.shape[1] == 1:
            # Mono 2D → stereo 2D
            audio_data = np.column_stack([audio_data[:, 0], audio_data[:, 0]])
        elif audio_data.shape[1] > 2:
            # #3743: ITU-R BS.775 downmix for multichannel sources.
            # Previously this took the first two channels via
            # `audio_data[:, :2].copy()`, which silently dropped Center
            # (vocals/dialogue), LFE, and surround content on 5.1 / 7.1
            # WAVs. The FFmpeg path (#3672) already applies the standard
            # matrix; downmix_to_stereo keeps the native loader
            # consistent with that behavior.
            audio_data = downmix_to_stereo(audio_data)

        info(f"Loaded {file_type}: {audio_data.shape[0]} samples, {sample_rate} Hz")
        return audio_data, sample_rate

    except ModuleError:
        # #4114: don't re-wrap already-specific ModuleError raises from the
        # loaders (ERROR_FFMPEG_TIMEOUT, ERROR_TRUNCATED_FILE, …) — propagate
        # them unchanged so callers/UI keep the diagnostic code. Sibling of
        # the #3695 passthrough in ffmpeg_loader.py / soundfile_loader.py.
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to load {file_type} file '{file_path}': {e}")
