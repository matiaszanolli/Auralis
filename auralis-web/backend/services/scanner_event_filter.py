"""Which filesystem events are worth a library rescan (#6164).

The watcher used to react to every event under a scan root, so a download's ``.part`` file, an
editor swap file or (with a broad root such as /tmp) the app's own temp WAVs kept the library
rescanning. A rescan can only change anything for an audio file, a cover image the artwork
fallback reads, or a directory appearing, disappearing or moving, so only those count; paths
inside the app's data directory and its stream/seekable temp files never do.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pathlib import Path
from typing import Any

from config.limits import SEEKABLE_TEMP_PREFIX, STREAM_TEMP_PREFIX

from auralis.io.formats import AUDIO_EXTENSIONS
from auralis.library.data_dir import get_data_dir

_COVER_SUFFIXES = frozenset({'.jpg', '.jpeg', '.png', '.webp'})
_RELEVANT_SUFFIXES = frozenset(AUDIO_EXTENSIONS) | _COVER_SUFFIXES


def _app_owned(path: Path) -> bool:
    """True for the app's own temp files and anything under its data directory."""
    if path.name.startswith((STREAM_TEMP_PREFIX, SEEKABLE_TEMP_PREFIX)):
        return True
    if any(part.startswith((STREAM_TEMP_PREFIX, SEEKABLE_TEMP_PREFIX)) for part in path.parts):
        return True
    try:
        return path.is_relative_to(get_data_dir())
    except (OSError, ValueError):
        return False


def is_relevant_event(event: Any) -> bool:
    """True when a watchdog event can change what a library scan would find."""
    src = getattr(event, 'src_path', None)
    if not src:  # not a path event we can judge: rescan rather than miss a change
        return True
    if getattr(event, 'is_directory', False):
        return not _app_owned(Path(str(src)))
    paths = [Path(str(p)) for p in (src, getattr(event, 'dest_path', '')) if p]
    return any(p.suffix.lower() in _RELEVANT_SUFFIXES and not _app_owned(p) for p in paths)
