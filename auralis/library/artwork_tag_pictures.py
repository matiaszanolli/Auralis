"""Pictures in the tag families mutagen exposes as plain key/value items (#5929).

ASF/WMA keeps covers in ``WM/Picture`` attributes and APEv2 (WavPack, Monkey's Audio) in
``Cover Art (...)`` binary items. Each reader returns ``(image bytes, mime type)`` or
``(None, None)`` and never raises.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import struct
from typing import Any

from .picture_choice import FRONT_COVER_TYPE

_MAGIC_MIME = ((b'\xff\xd8\xff', 'image/jpeg'), (b'\x89PNG\r\n\x1a\n', 'image/png'), (b'GIF8', 'image/gif'),
               (b'RIFF', 'image/webp'), (b'BM', 'image/bmp'))


def sniff_mime(data: bytes) -> str:
    """The image type of ``data`` from its leading bytes (tags rarely carry a trustworthy one)."""
    return next((mime for magic, mime in _MAGIC_MIME if data.startswith(magic)), 'image/jpeg')


def _asf_picture(raw: bytes) -> tuple[int, bytes]:
    """(picture type, image bytes) of one WM/Picture value: type, size, then two UTF-16 strings."""
    kind, size = struct.unpack_from('<BI', raw)
    pos = 5
    for _ in range(2):  # MIME type, description
        while raw[pos:pos + 2] != b'\x00\x00':
            pos += 2
        pos += 2
    return kind, raw[pos:pos + size]


def asf_picture(tags: Any) -> tuple[bytes | None, str | None]:
    """The front cover (else the first picture) from ASF ``WM/Picture`` attributes."""
    try:
        pictures = [_asf_picture(bytes(attr.value)) for attr in tags.get('WM/Picture', [])]
        pictures = [p for p in pictures if p[1]]
        if not pictures:
            return None, None
        _, data = next((p for p in pictures if p[0] == FRONT_COVER_TYPE), pictures[0])
        return data, sniff_mime(data)
    except Exception:
        return None, None


def ape_picture(tags: Any) -> tuple[bytes | None, str | None]:
    """The front cover (else any ``Cover Art`` item) from an APEv2 tag: ``name NUL image bytes``."""
    try:
        items = [k for k in tags.keys() if str(k).lower().startswith('cover art')]
        items.sort(key=lambda k: 'front' not in str(k).lower())
        for key in items:
            _, _, data = bytes(tags[key].value).partition(b'\x00')
            if data:
                return data, sniff_mime(data)
    except Exception:
        pass
    return None, None
