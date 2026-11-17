"""
Did a rescan find a different recording at this path? (split out of track_repository_mutation.py,
#6273)

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from ..models import Track

# Float-precision slack for comparing a stored REAL mtime with a fresh stat().
MTIME_TOLERANCE_SEC = 1e-3

# Fields that describe the audio itself. Compared against the stored row before
# a rescan overwrites it (#5719); "unknown" (None) on either side never counts
# as a change, so a pre-v22 row with no watermark is not re-analysed for nothing.
_AUDIO_FIELDS = ('filesize', 'duration', 'sample_rate', 'channels', 'format')
_DURATION_TOLERANCE_SEC = 0.01


def _audio_changed(track: Track, track_info: dict[str, Any]) -> bool:
    """True when a rescan shows the file at this path is not the one analysed.

    The stored fingerprint describes the audio that was on disk when it was
    computed. A re-rip, remaster or re-encode at the same path changes the
    file's size, duration, format or mtime; a tag edit changes size and mtime
    too, so it also re-fingerprints once (the cost of not hashing the audio).
    """
    for key in _AUDIO_FIELDS:
        old, new = getattr(track, key, None), track_info.get(key)
        if old is None or new is None:
            continue
        if key == 'duration':
            if abs(float(new) - float(old)) > _DURATION_TOLERANCE_SEC:
                return True
        elif new != old:
            return True
    old_mtime, new_mtime = track.file_mtime, track_info.get('file_mtime')
    return (
        old_mtime is not None and new_mtime is not None
        and abs(new_mtime - old_mtime) > MTIME_TOLERANCE_SEC
    )
