"""
Safe read of a candidate cover file from an album folder (#6160).

Album folders are untrusted: ``cover.jpg`` can be a symlink to a secret or to
``/dev/zero``, or a FIFO that blocks the scan forever. Only a regular file that
is not a symlink, within the size cap and starting with image magic bytes, is
read.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
import stat
from pathlib import Path

from ..utils.artwork_security import MAX_LOCAL_ARTWORK_BYTES, detect_image_extension


def read_folder_artwork(path: Path) -> bytes | None:
    """The file's bytes, or None when it is missing, special, oversized or not an image."""
    try:
        info = path.lstat()  # lstat: a symlink is refused, not followed
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_LOCAL_ARTWORK_BYTES:
            return None
        with open(path, 'rb') as f:
            data = f.read(MAX_LOCAL_ARTWORK_BYTES + 1)
    except OSError:
        return None
    if len(data) > MAX_LOCAL_ARTWORK_BYTES or not detect_image_extension(data, default=""):
        return None
    return data


# Highest priority first: the conventional names, then the Windows Media Player ones.
_COVER_STEMS = ('folder', 'cover', 'front', 'albumart', 'albumartsmall')
_COVER_EXTENSIONS = ('jpg', 'jpeg', 'png', 'webp')


def candidate_cover_files(album_dir: Path) -> list[Path]:
    """The album folder's cover files in priority order, matching names case-insensitively (#5929).

    A fixed list of spellings missed ``Cover.JPG`` and ``cover.webp`` on a case-sensitive
    filesystem; matching on the lower-cased directory listing finds whichever the folder has.
    """
    try:
        names = {entry.lower(): entry for entry in os.listdir(album_dir)}
    except OSError:
        return []
    wanted = (f"{stem}.{ext}" for stem in _COVER_STEMS for ext in _COVER_EXTENSIONS)
    return [album_dir / names[name] for name in wanted if name in names]
