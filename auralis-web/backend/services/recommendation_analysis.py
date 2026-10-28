"""
Cached, bounded mastering-recommendation analysis (#5970)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The one implementation behind both ``GET /api/player/mastering/recommendation/{id}`` and
``RecommendationService``, so a fix to the bound (#5248) or the cache key (#5956) lands once.
Callers validate the path first and own their error mapping: the route turns a
``TimeoutError`` into a 504 and ``None`` into a 422, the service logs and moves on.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any, cast

from cache import StreamlinedCacheManager
from core import audio_stream_controller as _asc
from schemas import DEFAULT_PRESET

logger = logging.getLogger(__name__)


async def cached_or_analyzed_recommendation(
    cache_manager: StreamlinedCacheManager,
    track_id: int,
    filepath: str,
    confidence_threshold: float,
) -> dict[str, Any] | None:
    """The cached recommendation, else a fresh bounded analysis (which is then cached).

    Returns ``None`` when the file could not be analysed; raises ``TimeoutError`` when the
    analysis exceeds ``CHUNK_PROCESS_TIMEOUT`` (a corrupt header or vanished storage can
    otherwise hang the worker thread and exhaust the shared I/O pool, #5248).
    """
    cached = cache_manager.get_mastering_recommendation(track_id, confidence_threshold)
    if cached is not None:
        logger.debug(f"Returning cached mastering recommendation for track {track_id}")
        return cached

    def _analyze() -> dict[str, Any] | None:
        from core.chunked_processor import ChunkedAudioProcessor

        processor = ChunkedAudioProcessor(
            track_id=track_id,
            filepath=filepath,
            preset=DEFAULT_PRESET,  # analysis only
            intensity=1.0,
            chunk_cache={},
        )
        rec = processor.get_mastering_recommendation(confidence_threshold=confidence_threshold)
        # to_response (not to_dict): carries track_id + is_hybrid (#3840).
        return cast(dict[str, Any], rec.to_response(track_id)) if rec is not None else None

    result = await asyncio.wait_for(asyncio.to_thread(_analyze), timeout=_asc.CHUNK_PROCESS_TIMEOUT)
    if result is not None:
        cache_manager.set_mastering_recommendation(track_id, result, confidence_threshold)
    return result
