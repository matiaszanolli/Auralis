"""
Memoize a probe's definitive answers only (split from ffmpeg_probe.py, #6318).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import functools
from collections.abc import Callable


def cache_definitive(probe: Callable[[], bool | None]) -> Callable[[], bool]:
    """Memoize a probe, but only a DEFINITIVE answer (#6318).

    ``probe`` returns True (present), False (absent) or None (it could not tell: a timeout on a
    cold first spawn, a non-zero exit, an OSError). None is reported as False for this call and
    NOT cached, so one slow spawn does not disable every FFmpeg format until restart.
    ``cache_clear()`` forces a re-probe, as ``lru_cache`` offered.
    """
    answer: list[bool] = []

    @functools.wraps(probe)
    def wrapper() -> bool:
        if answer:
            return answer[0]
        result = probe()
        if result is None:
            return False
        answer.append(result)
        return result

    wrapper.cache_clear = answer.clear  # type: ignore[attr-defined]
    return wrapper
