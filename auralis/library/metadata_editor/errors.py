"""
Metadata Editor Errors
~~~~~~~~~~~~~~~~~~~~~~

The one error callers see when mutagen cannot make sense of a file (#5993).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from mutagen import MutagenError
except ImportError:  # mutagen missing: there is nothing to open the file with either
    class MutagenError(Exception):  # type: ignore[no-redef]
        pass


class UnreadableAudioFileError(ValueError):
    """mutagen cannot identify or parse the file.

    A ``ValueError`` so existing ``except ValueError`` callers keep working. The
    message carries the file's basename only; HTTP layers must still answer with
    a fixed string rather than interpolate it.
    """


def open_audio_file(opener: Callable[[str], Any], filepath: str) -> Any:
    """Open ``filepath`` with ``opener`` (mutagen's ``File``), or raise
    ``UnreadableAudioFileError``.

    mutagen signals "not an audio file I know" as ``None`` for some containers
    and as a format-specific ``MutagenError`` (``FLACNoHeaderError``,
    ``HeaderNotFoundError``, ``InvalidChunk``, ...) for others; both become the
    same error, so a corrupt file fails identically whatever its extension.
    """
    try:
        audio_file = opener(filepath)
    except MutagenError as exc:
        raise UnreadableAudioFileError(
            f"Unsupported or invalid audio file: {Path(filepath).name}"
        ) from exc
    if audio_file is None:
        raise UnreadableAudioFileError(f"Unsupported or invalid audio file: {Path(filepath).name}")
    return audio_file
