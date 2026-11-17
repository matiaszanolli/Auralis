"""
Header-declared file size for the big-endian containers libsndfile cannot be asked about (#6315).

libsndfile clamps ``sf.info().frames`` to what is actually in an AIFF or AU file, so comparing it with
``len(sf.read())`` can never reveal a cut file. The container header still states how big the file
should be, which is what the WAV path already compares against.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import struct
from pathlib import Path

_AU_UNKNOWN_SIZE = 0xFFFFFFFF


def get_aiff_au_declared_size(file_path: Path) -> int | None:
    """The total size an AIFF/AIFC (``FORM`` chunk) or AU (``.snd``) header declares, or None.

    None when the file is neither, is too short to carry a header, or declares an unknown size (an AU
    data size of 0xFFFFFFFF, written by streaming encoders) so the truncation check is skipped rather
    than rejecting a valid file.
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)
    except OSError:
        return None
    if len(header) >= 12 and header[:4] == b'FORM' and header[8:12] in (b'AIFF', b'AIFC'):
        return int(struct.unpack('>I', header[4:8])[0]) + 8  # tag + size field
    if len(header) >= 12 and header[:4] == b'.snd':
        data_offset, data_size = struct.unpack('>II', header[4:12])
        if data_size == _AU_UNKNOWN_SIZE:
            return None
        return int(data_offset) + int(data_size)
    return None
