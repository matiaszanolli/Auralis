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
from pathlib import Path

from auralis.io.loaders.decode_temp import DECODE_TEMP_PREFIX
from core.dir_sweep import reap_older_than

logger = logging.getLogger(__name__)


def reclaim_leftover_decode_wavs(temp_root: Path, max_age_hours: float = 1.0) -> int:
    """Delete decode WAVs older than ``max_age_hours``; returns how many were removed."""
    reclaimed = reap_older_than(
        temp_root.glob(f"{DECODE_TEMP_PREFIX}*"), max_age_hours * 3600, label="leftover decode WAV", log=logger
    )
    if reclaimed:
        logger.info(f"🧹 Reclaimed {reclaimed} orphaned FFmpeg decode WAV(s)")
    return reclaimed
