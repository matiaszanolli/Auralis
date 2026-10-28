"""
FFmpeg input-path guard
~~~~~~~~~~~~~~~~~~~~~~~

Keeps a caller-supplied path from being parsed by libavformat as a protocol
(``pipe:``, ``concat:``, ``http://`` ...). Shared by the ffmpeg and ffprobe
call sites (#4834, #5733); split out of ffmpeg_probe.py to keep it under its
size ceiling.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
import re

from ...utils.logging import Code, ModuleError

# Matches any file_path libavformat would parse as a protocol rather than a
# path. A bare `"://" in path` check missed `pipe:0`, `concat:a|b`, `data:...`
# and every colon-only protocol (#4834). Two or more characters before the
# colon, so a single-letter Windows drive ("C:\\Users\\...") never matches.
_PROTOCOL_PREFIX_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.\-]+:')


def reject_protocol_path(file_path_str: str) -> None:
    """Raise ``ModuleError`` if *file_path_str* looks like an FFmpeg protocol
    specifier (``concat:``, ``pipe:``, ``http://``, ...) instead of a plain
    filesystem path (#4834)."""
    if _PROTOCOL_PREFIX_RE.match(file_path_str):
        raise ModuleError(
            f"{Code.ERROR_UNSUPPORTED_FORMAT}: URL/protocol inputs are not allowed",
            path=file_path_str,
        )


def ffmpeg_input_path(file_path_str: str) -> str:
    """The argv-safe form of an input path, for both ffmpeg and ffprobe (#5733).

    libavformat only parses a ``scheme:`` prefix at the START of the argument,
    so a relative name such as ``Live: Concert.mp3`` is read as a protocol while
    ``./Live: Concert.mp3`` is a file. A protocol-shaped name that really is a
    regular file is therefore anchored with ``./`` instead of refused; one that
    is not (``pipe:0``, ``concat:a|b``, ``https://...``) still raises.
    """
    if _PROTOCOL_PREFIX_RE.match(file_path_str) and os.path.isfile(file_path_str):
        return f"./{file_path_str}"
    reject_protocol_path(file_path_str)
    return file_path_str
