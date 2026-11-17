"""Startup sweep for the FFmpeg decoder's orphaned intermediate WAVs (#5734).

`auralis.io.loaders.ffmpeg_loader` decodes compressed formats into `auralis_decode_*.wav` files in the
system temp root. The `finally` that removes them cannot run after a SIGKILL or an OOM kill, and the
stream/seekable sweeps in tempfiles.py only glob directories under their own prefixes, so such a file
stayed for good (RAM, on a tmpfs /tmp). Like an untagged directory, it carries no owner, so only files
old enough not to be a live decode are removed.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import time
from pathlib import Path

from auralis.io.loaders.decode_temp import DECODE_TEMP_PREFIX

logger = logging.getLogger(__name__)


def reclaim_leftover_decode_wavs(temp_root: Path, max_age_hours: float = 1.0) -> int:
    """Delete decode WAVs older than ``max_age_hours``; returns how many were removed."""
    cutoff = time.time() - max_age_hours * 3600
    reclaimed = 0
    for leftover in temp_root.glob(f"{DECODE_TEMP_PREFIX}*"):
        try:
            if not leftover.is_file() or leftover.stat().st_mtime >= cutoff:
                continue
            leftover.unlink()
            reclaimed += 1
        except OSError as e:
            logger.warning(f"Failed to remove leftover decode WAV {leftover.name}: {type(e).__name__}")
    if reclaimed:
        logger.info(f"🧹 Reclaimed {reclaimed} orphaned FFmpeg decode WAV(s)")
    return reclaimed
