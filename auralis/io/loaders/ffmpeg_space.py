"""
Free-space guard for FFmpeg's intermediate WAV (#5734, #6166).

The decode is written to the temp root as float32 PCM - often a tmpfs, so RAM - and sat outside the
decoded-size budget, which counted only the array read back from it. Refusing a decode whose file
cannot fit, before FFmpeg starts, turns an out-of-space crash mid-write (or an OOM) into a clear error.
The estimate is the per-file cap's own, so no new threshold exists; what is already written counts
against the free space, and a margin absorbs concurrent decodes still being written.
"""

import errno
import shutil
import tempfile


FREE_SPACE_MARGIN_BYTES = 512 * 1024 * 1024


def require_decode_space(
    temp_folder: str | None, duration_s: float | None, sample_rate: int, channels: int
) -> None:
    """Raise ``OSError(ENOSPC)`` when the float32 WAV of ``duration_s`` cannot fit in the temp root."""
    from ..loader import estimated_decoded_bytes  # lazy: loader imports this package (a cycle otherwise)

    if not duration_s:
        return  # unknown length: the post-decode checks remain the backstop (#4128)
    needed = estimated_decoded_bytes(duration_s, sample_rate, channels) + FREE_SPACE_MARGIN_BYTES
    free = shutil.disk_usage(temp_folder or tempfile.gettempdir()).free
    if needed > free:
        gib = 1024 ** 3
        raise OSError(
            errno.ENOSPC,
            f"Not enough free space in the temp directory to decode this file "
            f"(needs about {needed / gib:.1f} GiB, {free / gib:.1f} GiB free)",
        )
