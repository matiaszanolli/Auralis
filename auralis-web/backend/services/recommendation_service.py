"""
Recommendation Service

Generates and broadcasts mastering recommendations based on audio analysis.
Performs background analysis of loaded tracks to suggest optimal audio profiles.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import logging
import os
import sys
from typing import Any, Protocol, cast

logger = logging.getLogger(__name__)


class BroadcastManager(Protocol):
    """Protocol for broadcast manager interface."""

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast message to connected clients."""
        ...


class RecommendationService:
    """
    Service for generating audio mastering recommendations.

    Analyzes track characteristics to recommend optimal enhancement profiles.
    Broadcasts recommendations via WebSocket to connected clients.
    """

    def __init__(self, connection_manager: BroadcastManager) -> None:
        """
        Initialize RecommendationService.

        Args:
            connection_manager: WebSocket connection manager for broadcasts

        Raises:
            ValueError: If connection_manager is not available
        """
        self.connection_manager: BroadcastManager = connection_manager

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
        # ChunkedAudioProcessor.__init__ + get_mastering_recommendation are
        # synchronous and can take several seconds (full audio decode +
        # librosa analysis if the fingerprint isn't cached). Run the
        # whole sync chain in a thread so the event loop stays responsive
        # (fixes #3553 / BE-NEW-95). FastAPI BackgroundTasks schedules
        # async coroutines on the SAME event loop as the request — without
        # this offload, every track-load froze the backend.
        def _analyze() -> dict[str, Any] | None:
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from core.chunked_processor import ChunkedAudioProcessor

            processor = ChunkedAudioProcessor(
                track_id=track_id,
                filepath=track_path,
                preset="adaptive",
                intensity=1.0,
                chunk_cache={},
            )
            rec = processor.get_mastering_recommendation(
                confidence_threshold=confidence_threshold
            )
            if rec is None:
                return None
            rec_dict = cast(dict[str, Any], rec.to_dict())
            rec_dict['track_id'] = track_id
            rec_dict['is_hybrid'] = bool(rec_dict.get('weighted_profiles'))
            return rec_dict

        try:
            rec_dict = await asyncio.to_thread(_analyze)
            if rec_dict:
                await self.connection_manager.broadcast({
                    "type": "mastering_recommendation",
                    "data": rec_dict,
                })
                logger.info(f"📊 Broadcasted mastering recommendation for track {track_id}")
                return rec_dict
            logger.info(f"ℹ️  No confident recommendation found for track {track_id}")
            return {}
        except Exception as e:
            # Log but don't fail - recommendations are optional
            logger.warning(f"Failed to generate mastering recommendation for track {track_id}: {e}")
            return {}

    async def get_recommendation_for_track(
        self,
        track_id: int,
        track_path: str,
        confidence_threshold: float = 0.4
    ) -> dict[str, Any] | None:
        """
        Get mastering recommendation for a track without broadcasting.

        Useful for frontend queries about recommendations.

        Args:
            track_id: Track database ID
            track_path: Path to audio file
            confidence_threshold: Minimum confidence for recommendation

        Returns:
            dict: Recommendation data if available, None otherwise

        Raises:
            Exception: If analysis fails
        """
        # Same offload pattern as generate_and_broadcast_recommendation
        # (fixes #3553 / BE-NEW-95) — sync work runs in a thread.
        def _analyze() -> dict[str, Any] | None:
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from core.chunked_processor import ChunkedAudioProcessor

            processor = ChunkedAudioProcessor(
                track_id=track_id,
                filepath=track_path,
                preset="adaptive",
                intensity=1.0,
                chunk_cache={},
            )
            rec = processor.get_mastering_recommendation(
                confidence_threshold=confidence_threshold
            )
            if rec is None:
                return None
            rec_dict = cast(dict[str, Any], rec.to_dict())
            rec_dict['track_id'] = track_id
            rec_dict['is_hybrid'] = bool(rec_dict.get('weighted_profiles'))
            return rec_dict

        try:
            return await asyncio.to_thread(_analyze)
        except Exception as e:
            logger.error(f"Failed to get mastering recommendation for track {track_id}: {e}")
            raise
