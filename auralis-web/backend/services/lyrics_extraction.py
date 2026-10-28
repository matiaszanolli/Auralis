"""
Embedded-lyrics extraction (#5939)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``GET /api/library/tracks/{id}/lyrics`` falls back to reading the file's tags.
The route used ``str(tags['LYRICS'])`` for every non-MP4 container, but FLAC /
Ogg / Opus Vorbis comments return a *list* of strings, so the stored text was
``"['line text']"`` (and was then persisted and served forever). The
``UNSYNCEDLYRICS`` convention most Vorbis taggers use was unreachable, and an ID3
file was only probed for an English USLT frame.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import re
from typing import Any

# A synced (LRC) line starts with a [mm:ss] or [mm:ss.xx] timestamp. A bare "[" and
# "]" pair is also found in plain lyrics ("[Chorus]"), so it is not a signal.
_LRC_TIMESTAMP = re.compile(r"\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]")

_VORBIS_LYRICS_KEYS = ("LYRICS", "UNSYNCEDLYRICS", "SYNCEDLYRICS")


def lyrics_format(text: str) -> str:
    """``"lrc"`` for timestamped lyrics, otherwise ``"plain"``."""
    return "lrc" if _LRC_TIMESTAMP.search(text) else "plain"


def _first_text(value: Any) -> str | None:
    """A tag value as text: the first non-empty entry of a list, else the string."""
    if isinstance(value, (list, tuple)):
        value = next((v for v in value if v), None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_embedded_lyrics(audio_file: Any) -> str | None:
    """Lyrics text from a mutagen file object, or None when the file has none."""
    from mutagen.mp4 import MP4

    if isinstance(audio_file, MP4):
        # iTunes '©lyr' atom; MP4Tags also implements .get(), so test the type first (#2383).
        return _first_text(audio_file.get("\xa9lyr"))  # type: ignore[no-untyped-call]

    tags = getattr(audio_file, "tags", None)
    if not tags:
        return None

    # ID3: any USLT frame (the language and description are part of the key).
    getall = getattr(tags, "getall", None)
    if getall is not None:
        for frame in getall("USLT"):
            text = _first_text(getattr(frame, "text", None))
            if text:
                return text
        return None

    # Vorbis comments (FLAC / Ogg / Opus): values are lists, keys case-insensitive.
    for key in _VORBIS_LYRICS_KEYS:
        try:
            text = _first_text(tags.get(key))
        except (KeyError, ValueError, AttributeError):
            text = None
        if text:
            return text
    return None
