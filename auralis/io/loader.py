"""
Auralis Audio Loader
~~~~~~~~~~~~~~~~~~~~

Audio file loading and validation

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Refactored from Matchering 2.0 by Sergree and contributors
"""


import math as _math
from pathlib import Path

import numpy as np

from ..utils.logging import debug, info
from .formats import FFMPEG_FORMATS
from .loaders import load_with_ffmpeg, load_with_soundfile
from .processing import validate_audio


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


def oversize_probe_detail(
    duration_seconds: float | None,
    sample_rate: int | None,
    channels: int | None,
) -> str | None:
    """Message describing why a *probed* file must be refused, or None if it is fine.

    The decode paths (:func:`load`, ``unified_loader.load_audio``,
    ``ffmpeg_loader.load_with_ffmpeg``, ``soundfile_loader``) have always
    enforced ``MAX_DURATION_SECONDS`` plus :func:`oversize_decode_detail`, but
    the metadata-only probes did not: ``unified_loader.get_audio_info()`` and
    the library scanner returned whatever duration the container claimed
    (#5312). A forged or corrupt header (e.g. a bogus Xing/VBRI frame count)
    then propagated into ``content_chunk_count()`` and drove an unbounded
    per-chunk loop of silence, logging and DSP work past real EOF.

    This is the single definition of "the probe says this file is out of
    bounds" so every probe path applies the identical rule — a probe path that
    grew its own copy is exactly how the two ffprobe implementations drifted
    apart in the first place.

    ``sample_rate``/``channels`` may be None or 0 when the probe could not
    determine them; the decoded-size half then degrades to a no-op and the
    duration ceiling still applies. A ``None`` duration means "unknown", which
    is not a rejection — see ffmpeg_loader's size-implied fallback (#4128).
    """
    if duration_seconds is None:
        return None
    duration = float(duration_seconds)
    # A forged header can report NaN/Inf, which slips past every `>` comparison
    # and then blows up int() conversion further down.
    if not _math.isfinite(duration):
        return f"Audio file reports a non-finite duration ({duration_seconds!r})"
    if duration > MAX_DURATION_SECONDS:
        return (
            f"Audio file exceeds maximum duration "
            f"({duration:.0f}s > {MAX_DURATION_SECONDS}s)"
        )
    return oversize_decode_detail(duration, sample_rate or 0, channels or 1)


def load(file_path: str, file_type: str = "audio") -> tuple[np.ndarray, int]:
    """
    Load an audio file for the player: validated, float32, stereo 2-D.

    Args:
        file_path: Path to the audio file
        file_type: Type of file being loaded ("target", "reference", or "audio")

    Returns:
        tuple: (audio_data, sample_rate)

    Raises:
        ModuleError: From the shared decode paths — truncation, budget and
            duration ceilings, decode failures (#4114 passthrough).
    """
    debug(f"Loading {file_type} file: {file_path}")

    # Route FFmpeg-required formats (M4A, AAC, WMA, OPUS, MP3, OGG) through
    # FFmpeg; use the shared soundfile loader for natively supported formats.
    # #5589: this function used to keep its own sf.read branch, which skipped
    # every check the shared paths apply — a truncated WAV played as a short
    # clip with no diagnostic (libsndfile adjusts frame counts to the data
    # actually present, so this branch's frames comparison could never fire
    # for WAV), NaN/Inf samples reached the playback chain, and a zero-frame
    # file loaded as an empty buffer. The shared loaders carry the RIFF/FLAC
    # truncation detection, the duration and decoded-size budgets and the
    # layout-aware routing; validate_audio then applies the same empty /
    # NaN-sanitising / dtype checks unified_loader.load_audio makes for every
    # other decode.
    file_ext = Path(file_path).suffix.lower()
    if file_ext in FFMPEG_FORMATS:
        audio_data, sample_rate = load_with_ffmpeg(Path(file_path))
    else:
        audio_data, sample_rate = load_with_soundfile(Path(file_path))

    audio_data, sample_rate = validate_audio(audio_data, sample_rate, file_type)

    # Player contract: stereo 2-D float32 (validate_audio normalised dtype).
    if audio_data.ndim == 1:
        # Mono 1D → stereo 2D
        audio_data = np.column_stack([audio_data, audio_data])
    elif audio_data.shape[1] == 1:
        # Mono 2D → stereo 2D
        audio_data = np.column_stack([audio_data[:, 0], audio_data[:, 0]])

    info(f"Loaded {file_type}: {audio_data.shape[0]} samples, {sample_rate} Hz")
    return audio_data, sample_rate
