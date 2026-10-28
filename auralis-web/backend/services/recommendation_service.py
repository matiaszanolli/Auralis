"""
Recommendation Service

Generates and broadcasts mastering recommendations based on audio analysis.
Performs background analysis of loaded tracks to suggest optimal audio profiles.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any, cast

from cache import StreamlinedCacheManager, streamlined_cache_manager
from security.path_security import PathValidationError, validate_file_path
from core import audio_stream_controller as _asc
from services.recommendation_analysis import cached_or_analyzed_recommendation
from websocket.outbound.enhancement import MasteringRecommendationPayload
from websocket.outbound_messages import BroadcastManager, broadcast_typed

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Service for generating audio mastering recommendations.

    Analyzes track characteristics to recommend optimal enhancement profiles.
    Broadcasts recommendations via WebSocket to connected clients.
    """

    def __init__(
        self,
        connection_manager: BroadcastManager,
        cache_manager: StreamlinedCacheManager = streamlined_cache_manager,
    ) -> None:
        """
        Initialize RecommendationService.

        Args:
            connection_manager: WebSocket connection manager for broadcasts
            cache_manager: Shared recommendation cache

        Raises:
            ValueError: If connection_manager is not available
        """
        self.connection_manager: BroadcastManager = connection_manager
        self.cache_manager = cache_manager

    async def _get_or_analyze(
        self,
        track_id: int,
        track_path: str,
        confidence_threshold: float,
    ) -> dict[str, Any] | None:
        """Return a cached recommendation or run the bounded analysis."""
        # #4817: POST /api/player/load schedules this with the DB filepath on
        # every load, so this is the reachable path, not the REST endpoint.
        # Both public methods funnel through here; re-check before any I/O.
        try:
            track_path = str(validate_file_path(str(track_path)))
        except PathValidationError:
            logger.debug(
                f"Not analysing track {track_id}: stored filepath failed validation"
            )
            return None
        return await cached_or_analyzed_recommendation(
            self.cache_manager, track_id, track_path, confidence_threshold
        )

    async def generate_and_broadcast_recommendation(
        self,
        track_id: int,
        track_path: str,
        confidence_threshold: float = 0.4
    ) -> dict[str, Any]:
        """
        Generate mastering recommendation for a track and broadcast via WebSocket.

        This is non-blocking - if analysis fails, playback continues normally.
        Generates recommendation asynchronously for better UX.

        Args:
            track_id: Track database ID
            track_path: Path to audio file
            confidence_threshold: Minimum confidence for recommendation (0.0-1.0)

        Returns:
            dict: Recommendation data if successful, empty dict if analysis fails

        Raises:
            Exception: If critical error occurs (not recommended errors are ignored)
        """
        try:
            # #5248: bound the same way every streaming entry point bounds
            # ChunkedAudioProcessor construction — sf.info() has no timeout
            # of its own for natively-decodable formats, so a corrupt header
            # or a track on storage that disappears mid-read can otherwise
            # hang this thread forever and, since this fires on every play,
            # eventually exhaust the shared IO_EXECUTOR pool.
            rec_dict = await self._get_or_analyze(
                track_id, track_path, confidence_threshold
            )
            if rec_dict:
                await broadcast_typed(
                    self.connection_manager,
                    "mastering_recommendation",
                    cast(MasteringRecommendationPayload, rec_dict),
                )
                logger.info(f"📊 Broadcasted mastering recommendation for track {track_id}")
                return rec_dict
            logger.info(f"ℹ️  No confident recommendation found for track {track_id}")
            return {}
        except TimeoutError:
            # Recommendations are optional — a hung analysis should degrade
            # exactly like an analysis failure, not propagate.
            logger.warning(
                f"Mastering recommendation analysis timed out after "
                f"{_asc.CHUNK_PROCESS_TIMEOUT}s for track {track_id}"
            )
            return {}
        except Exception as e:
            # Log but don't fail - recommendations are optional
            logger.warning(f"Failed to generate mastering recommendation for track {track_id}: {e}")
            return {}
