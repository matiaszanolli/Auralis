"""
FFmpeg decode bounds set by policy, not by the file's header (#6511)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every size guard on the FFmpeg path (the duration cap, the decoded-size cap, the free-space check)
was computed from ffprobe's *declared* duration, and the decode itself ran unbounded. A file whose
header under-reports its real stream length (30 s declared, hours real) passed them all and wrote
gigabytes of float32 WAV, at about 1.3 GB/s, before anything noticed. The decode is now bounded by
policy: ``-t`` at a margin over the declared length (never past ``MAX_DURATION_SECONDS``) and ``-fs``
at the decoded-size cap. A result that reached either bound means the header lied, so the WAV is
rejected.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path

import soundfile as sf

from ...utils.logging import Code, ModuleError

# Real streams overrun their declared duration a little (VBR estimates, priming frames).
DECLARED_DURATION_MARGIN = 1.25
DECLARED_DURATION_SLACK_S = 30.0
# A decode that stops within this of its time cap ran into it.
_CAP_REACHED_TOLERANCE_S = 0.5


def decode_cap_seconds(expected_duration: float | None, window: float | None) -> float:
    """How many seconds FFmpeg may decode: the caller's window, else the declared length plus margin."""
    from ..loader import MAX_DURATION_SECONDS  # lazy: loader imports this package (a cycle otherwise)

    if window:
        return float(window)
    if not expected_duration:
        return float(MAX_DURATION_SECONDS)
    return min(expected_duration * DECLARED_DURATION_MARGIN + DECLARED_DURATION_SLACK_S, float(MAX_DURATION_SECONDS))


def size_limit_args() -> list[str]:
    """FFmpeg's output size limit: never write more than the decoded-size cap."""
    from ..loader import MAX_DECODED_BYTES

    return ["-fs", str(MAX_DECODED_BYTES)]


def check_decode_bounds(temp_wav: Path, cap_seconds: float, windowed: bool, path: str) -> None:
    """Raise ModuleError when the decode ran into the size cap, or (unwindowed) into its time cap."""
    from ..loader import MAX_DECODED_BYTES

    if temp_wav.stat().st_size >= MAX_DECODED_BYTES:
        raise ModuleError(
            f"{Code.ERROR_FFMPEG_CONVERSION}: Decoded audio reached the maximum decoded size "
            f"({MAX_DECODED_BYTES / 1024 ** 3:.1f} GiB); the file's declared length is wrong",
            path=path,
        )
    if windowed:
        return  # the caller asked for exactly this much
    info = sf.info(str(temp_wav))
    decoded_seconds = info.frames / info.samplerate if info.samplerate else 0.0
    if decoded_seconds >= cap_seconds - _CAP_REACHED_TOLERANCE_S:
        raise ModuleError(
            f"{Code.ERROR_FFMPEG_CONVERSION}: Audio stream runs past {cap_seconds:.0f}s, longer than its "
            f"header declares or than the maximum duration allows",
            path=path,
        )
