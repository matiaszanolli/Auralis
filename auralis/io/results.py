"""
Auralis Results and Output Handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Result types and output format specifications

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""

import os
from pathlib import Path

import soundfile as sf


class Result:
    """Represents an output result with format specifications.

    A ``Result`` only describes the output target (path + PCM subtype); it does
    not transform audio. There is no ``Result.write()`` — the writer
    (``simple_mastering.process_to_file`` / ``saver.py``) reads ``file`` and
    ``subtype`` only. Callers are responsible for clamping samples to
    ``[-1.0, 1.0]`` before writing (saver.py also clamps before PCM encode).

    #4106: the former ``use_limiter`` / ``normalize`` flags were removed — they
    were stored but never read by any code path, advertising a false
    auto-limit / normalize contract.
    """

    def __init__(
        self,
        file: str,
        subtype: str = 'PCM_16',
    ):
        """
        Initialize a Result object

        Args:
            file: Output file path
            subtype: Audio format subtype (PCM_16, PCM_24, etc.)
        """
        file_ext = Path(file).suffix[1:].upper()

        if not sf.check_format(file_ext):
            raise TypeError(f"{file_ext} format is not supported")
        if not sf.check_format(file_ext, subtype):
            raise TypeError(f"{file_ext} format does not have {subtype} subtype")

        # #3756: fail early on bad output paths. The previous behavior
        # delayed the error until `sf.SoundFile(..., mode='w')` was
        # opened in `simple_mastering.process_to_file` — after a
        # half-hour of CPU. Check that the parent directory exists
        # and is writable before any of that work happens.
        parent = Path(file).parent
        if not parent.exists():
            raise FileNotFoundError(
                f"Output directory does not exist: {parent}"
            )
        if not os.access(parent, os.W_OK):
            raise PermissionError(
                f"Output directory is not writable: {parent}"
            )

        self.file = file
        self.subtype = subtype

    def __repr__(self) -> str:
        return f"Result(file='{self.file}', subtype='{self.subtype}')"


def pcm16(file: str) -> Result:
    """Create a 16-bit PCM result"""
    return Result(file, "PCM_16")


def pcm24(file: str) -> Result:
    """Create a 24-bit PCM result"""
    return Result(file, "PCM_24")