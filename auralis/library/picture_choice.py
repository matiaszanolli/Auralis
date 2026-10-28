"""
Which of a file's embedded pictures is the album art (#5929).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

# ID3 APIC / FLAC picture type 3: "Cover (front)".
FRONT_COVER_TYPE = 3


def front_cover_first(pictures: Any) -> Any:
    """The front-cover picture, else the first one (#5929).

    Files often list a back cover, booklet page or artist photo ahead of the front cover, and
    taking the first picture then made that the album art. Works on any picture with ``.type``.
    """
    pictures = list(pictures)
    return next((p for p in pictures if getattr(p, 'type', None) == FRONT_COVER_TYPE), pictures[0])
