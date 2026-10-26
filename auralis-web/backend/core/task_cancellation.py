"""
Awaiting a task you have just cancelled, without losing your own cancellation.

``task.cancel(); try: await task; except CancelledError: pass`` cannot tell "the
worker finished handling its cancellation" from "I am being cancelled too": both
surface as ``CancelledError`` at the ``await``. Swallowing the second lets a
cancelled HTTP request or a twice-cancelled shutdown run on into the steps it
was told to abandon (#4809, #5083, #6092). ``Task.cancelling()`` is non-zero
only when a cancellation targets the *current* task, which is the test used here.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any


def caller_is_being_cancelled() -> bool:
    """Whether the *current* task has a cancellation of its own pending (#5083).

    False when not running inside a Task, where there is no caller cancellation to keep.
    """
    current = asyncio.current_task()
    return current is not None and current.cancelling() > 0


async def await_cancelled_task(
    task: "asyncio.Task[Any]", logger: logging.Logger | None = None
) -> None:
    """Await a task the caller already called ``.cancel()`` on.

    Swallows the awaited task's own teardown outcome (its CancelledError or any
    exception it raised) but re-raises when the CURRENT task is itself being
    cancelled.
    """
    try:
        await task
    except asyncio.CancelledError:
        if caller_is_being_cancelled():
            raise
    except Exception:
        if logger is not None:
            logger.debug("Prior task raised while awaiting its cancellation", exc_info=True)
