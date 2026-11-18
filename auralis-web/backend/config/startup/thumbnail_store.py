"""Startup sweep of the thumbnail cache (#6439).

Per-render maintenance is throttled to one sweep per N renders, so a session that renders
fewer than N thumbnails never sweeps. This reaps orphaned ``.tmp-*`` files and re-applies
the size cap once per launch, off the event loop.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging

from core.thumbnail_cache import artwork_cache_dirs
from core.thumbnail_sweep import sweep_thumbnail_cache

logger = logging.getLogger(__name__)


async def sweep_thumbnail_store() -> int:
    """Reap and prune the thumbnail cache; a failure is logged, never fatal to startup."""
    try:
        _artwork_dir, thumb_dir = artwork_cache_dirs()
        deleted, _reclaimed = await asyncio.to_thread(sweep_thumbnail_cache, thumb_dir)
        return deleted
    except Exception as e:  # noqa: BLE001 - housekeeping must not block the app starting
        logger.warning(f"Thumbnail cache sweep failed: {type(e).__name__}")
        return 0
