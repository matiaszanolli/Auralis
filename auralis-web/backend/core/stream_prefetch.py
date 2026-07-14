#!/usr/bin/env python3

"""
Stream Next-Track Prefetch
~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-processes the first chunk of the next queued track to eliminate
cold-start delay on track transitions. Currently not called from the
production streaming entry points (disabled in #3513 / BE-NEW-55, see
docstring below) but exercised directly by tests, so it must remain
callable exactly as before.

Extracted from audio_stream_controller.py (#4071).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .chunk_cache import SimpleChunkCache
from .file_signature import FileSignatureService

if TYPE_CHECKING:
    from .audio_stream_controller import AudioStreamController

logger = logging.getLogger(__name__)


async def prefetch_next_track(
    controller: 'AudioStreamController',
    current_track_id: int,
    preset: str,
    intensity: float,
) -> None:
    """
    Pre-process the first chunk of the next track in queue.

    Called at ~80% progress of the current track to eliminate cold-start
    delay on track transitions. Silently fails — this is an optimization,
    not a requirement.

    Populates the chunk cache so next track's chunk 0 is a cache hit, and
    queues fingerprint generation in background.
    """
    if not controller._get_repository_factory or not controller.chunked_processor_class:
        return

    try:
        factory = controller._get_repository_factory()
        queue_state = factory.queue.get_queue_state()
        if not queue_state or not queue_state.track_ids:
            return

        # Parse track IDs and find next track
        import json as _json
        track_ids: list[int] = _json.loads(queue_state.track_ids)
        if not track_ids:
            return

        current_idx = queue_state.current_index
        # Find the current track in the queue
        try:
            pos = track_ids.index(current_track_id)
            next_idx = pos + 1
        except ValueError:
            # Current track not in queue — use current_index + 1
            next_idx = current_idx + 1

        if next_idx >= len(track_ids):
            # Check repeat mode
            if queue_state.repeat_mode == 'all':
                next_idx = 0
            else:
                return  # No next track

        next_track_id = track_ids[next_idx]
        next_track = await asyncio.to_thread(factory.tracks.get_by_id, next_track_id)
        if not next_track or not Path(next_track.filepath).exists():
            return

        logger.info(f"Pre-fetching next track {next_track_id} (chunk 0)")

        # Queue fingerprint generation in background
        await controller._check_or_queue_fingerprint(
            track_id=next_track_id,
            filepath=str(next_track.filepath),
            websocket=None,
        )

        # Check if chunk 0 is already cached. Compute the file signature the
        # same way the ChunkedAudioProcessor will (below), so this pre-fetch
        # lookup and the eventual put() agree on the key — and so a changed
        # file misses instead of returning stale audio (#4358).
        file_signature = await asyncio.to_thread(
            FileSignatureService.generate, str(next_track.filepath)
        )
        if isinstance(controller.cache_manager, SimpleChunkCache):
            cached = controller.cache_manager.get(
                track_id=next_track_id, chunk_idx=0,
                preset=preset, intensity=intensity,
                file_signature=file_signature,
            )
            if cached:
                logger.info(f"Next track {next_track_id} chunk 0 already cached")
                return

        # Clear any stale tail from a previous play of this track (#3527)
        await controller._drop_chunk_tail(next_track_id)

        # Create processor and process chunk 0 (populates cache)
        processor = await asyncio.to_thread(
            controller.chunked_processor_class,
            track_id=next_track_id,
            filepath=str(next_track.filepath),
            preset=preset,
            intensity=intensity,
        )
        await controller._process_chunk_only(0, processor)
        logger.info(f"Pre-fetched next track {next_track_id} chunk 0 into cache")

    except Exception as e:
        # Silent failure — prefetch is an optimization
        logger.debug(f"Next-track prefetch failed (not critical): {e}")
