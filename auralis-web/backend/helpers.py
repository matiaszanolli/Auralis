"""
Backend Helpers
~~~~~~~~~~~~~~~

Small shared utilities used across the backend:

- fire-and-forget asyncio task spawning (#3512)
- library-scan progress computation (#4409, #4411)
- enhancement-settings seeding (#4409)

#4606: the pagination / batch-operation / filter-search / cache-response
cluster that previously lived here (14 functions) was deleted — it had zero
production callers and was exercised only by tests, while routers shipped
ad-hoc dict literals for the same concepts. `routers/pagination.py` is a
separate dead pagination implementation, tracked by #3892.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any

from schemas import VALID_PRESETS

logger = logging.getLogger(__name__)


# ============================================================================
# Fire-and-forget asyncio task helpers (fixes #3512 / BE-NEW-54)
# ============================================================================

def log_task_exception(task: asyncio.Task[Any]) -> None:
    """Log an uncaught exception raised by a background task.

    Pair with `asyncio.create_task(coro).add_done_callback(log_task_exception)`
    so that fire-and-forget tasks don't silently disappear when they raise.
    A swallowed exception in start_worker / next_track / progress callbacks
    would otherwise stop the entire feature without any log entry.
    """
    try:
        if task.cancelled():
            return
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is None:
        return
    name = task.get_name() or repr(task)
    logger.error("Background task %s failed", name, exc_info=exc)


def spawn_background_task(coro: Any, *, name: str | None = None) -> asyncio.Task[Any]:
    """Schedule a coroutine as a background task with exception logging.

    Equivalent to:
        t = asyncio.create_task(coro, name=name)
        t.add_done_callback(log_task_exception)
        return t

    Prefer this over bare `asyncio.create_task(coro)` for any fire-and-forget
    work whose failure shouldn't go unnoticed (fixes #3512).
    """
    task: asyncio.Task[Any] = asyncio.create_task(coro, name=name) if name else asyncio.create_task(coro)
    task.add_done_callback(log_task_exception)
    return task



# ============================================================================
# Library-scan helpers (#4409, #4411, #4616)
# ============================================================================

def scan_progress_percentage(progress_data: dict[str, Any]) -> int | None:
    """Compute the scan progress percentage, or ``None`` when indeterminate.

    The streaming scanner interleaves discovery and processing, so
    ``total_found`` only reflects files seen so far (≈ ``processed`` at every
    checkpoint) and ``processed / total`` is always ~100% — a meaningless
    determinate bar. Return a real percentage only when the scanner supplies a
    ``progress`` fraction; otherwise ``None`` so the UI shows an indeterminate
    bar plus the climbing count (#4411 / F4-04). The scanner establishes that
    fraction against a pre-counted total (#4616). Shared by the manual-scan and
    auto-scan progress emitters.

    ``0.0`` is a real fraction, not a missing one: the guard tests for ``None``
    rather than truthiness, so the first frame of a scan renders as 0%, not as
    indeterminate (#4616).
    """
    frac = progress_data.get('progress')
    if not isinstance(frac, (int, float)) or isinstance(frac, bool):
        return None
    return round(max(0.0, min(float(frac), 1.0)) * 100)


def seed_enhancement_settings(
    enhancement_settings: dict[str, Any], user_settings: Any
) -> None:
    """Seed the runtime ``enhancement_settings`` dict from persisted settings.

    Maps ``default_preset`` → ``preset``, ``enhancement_intensity`` →
    ``intensity`` and ``auto_enhance`` → ``enabled`` so a user's saved
    enhancement defaults actually affect playback (#4409). Mutates
    ``enhancement_settings`` in place — routers capture this exact dict object.
    ``user_settings`` may be ``None`` (nothing to seed).
    """
    if user_settings is None:
        return
    stored_preset = getattr(user_settings, 'default_preset', None)
    if stored_preset:
        # `default_preset` is a plain String column, so a legacy or
        # hand-edited row can hold a value outside the canonical set. Since
        # #4710 typed EnhancementSettings.preset as EnhancementPresetLiteral,
        # seeding an off-list value here would turn every
        # GET /api/player/enhancement/status into a response-validation 500.
        # Degrade to the default and say so instead — the same tolerance the
        # WS command path already applies (playback_commands.py).
        if stored_preset in VALID_PRESETS:
            enhancement_settings['preset'] = stored_preset
        else:
            logger.warning(
                f"Stored default_preset {stored_preset!r} is not one of "
                f"{VALID_PRESETS}; keeping "
                f"{enhancement_settings.get('preset', 'adaptive')!r}"
            )
    intensity = getattr(user_settings, 'enhancement_intensity', None)
    if intensity is not None:
        enhancement_settings['intensity'] = float(intensity)
    enhancement_settings['enabled'] = bool(getattr(user_settings, 'auto_enhance', True))
