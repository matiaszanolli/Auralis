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

# A path libavformat would parse as a protocol (`pipe:0`, `concat:a|b`, `data:...`; #4834): two or more
# characters before the colon, so a single-letter Windows drive ("C:\\Users") never matches.
_PROTOCOL_PREFIX_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.\-]+:')
# libavformat's own scheme rule (any [A-Za-z0-9+.-] run, digit first): decides the "./" anchor (#6317).
_SCHEME_LIKE_RE = re.compile(r'^[A-Za-z0-9+.\-]+:')


def reject_protocol_path(file_path_str: str) -> None:
    """Raise ``ModuleError`` if *file_path_str* looks like an FFmpeg protocol specifier (#4834)."""
    if _PROTOCOL_PREFIX_RE.match(file_path_str):
        raise ModuleError(
            f"{Code.ERROR_UNSUPPORTED_FORMAT}: URL/protocol inputs are not allowed",
            path=file_path_str,
        )


def ffmpeg_input_path(file_path_str: str) -> str:
    """The argv-safe form of an input path, for ffmpeg and ffprobe (#5733).

    libavformat parses a ``scheme:`` prefix only at the START of the argument, so a relative regular file
    such as ``Live: Concert.mp3`` is anchored as ``./Live: Concert.mp3``; a real protocol still raises.
    """
    if (
        _SCHEME_LIKE_RE.match(file_path_str)
        and not os.path.isabs(file_path_str)  # a Windows "C:\\..." drive path is absolute, not a scheme
        and os.path.isfile(file_path_str)
    ):
        return f"./{file_path_str}"
    reject_protocol_path(file_path_str)
    return file_path_str
