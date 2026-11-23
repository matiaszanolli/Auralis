"""
Closing a ChunkedAudioProcessor off the event loop (#6550)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ChunkedAudioProcessor.close()`` releases its converted temp WAV, and a release that pushes the
idle conversions over the cap rmtrees a full-track WAV (``ConvertedWavRegistry`` is off-loop only):
run on the event loop it stalled every WebSocket. Used by the streamlined worker's drop paths
(``streamlined_processor_disposal.py``) and its ``stop()``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Closes running off the loop; strong references until they finish.
_pending_closes: set[asyncio.Task[None]] = set()


def _close_blocking(label: Any, processor: Any) -> None:
    try:
        processor.close()
    except Exception as exc:
        logger.warning(f"Failed to close dropped processor {label}: {exc}")


def close_off_loop(label: Any, processor: Any) -> None:
    """Close ``processor`` in a worker thread when called on the event loop, else inline. Never raises."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        _close_blocking(label, processor)  # already off the loop
        return
    task = asyncio.ensure_future(asyncio.to_thread(_close_blocking, label, processor))
    _pending_closes.add(task)
    task.add_done_callback(_pending_closes.discard)


async def wait_for_pending_closes() -> None:
    """Return once every close started off the loop has finished (worker stop, tests)."""
    while _pending_closes:
        await asyncio.gather(*list(_pending_closes))
