"""
Cache Management API Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

API endpoints for multi-tier buffer cache management and statistics.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics."""
    l1: Dict[str, Any]
    l2: Dict[str, Any]
    l3: Dict[str, Any]
    overall: Dict[str, Any]
    prediction: Dict[str, Any]


class PresetPrediction(BaseModel):
    """Model for preset prediction."""
    preset: str
    probability: float


class PredictionsResponse(BaseModel):
    """Response model for preset predictions."""
    current_preset: str
    current_position: float
    predictions: List[PresetPrediction]


class CacheEntryInfo(BaseModel):
    """Information about a cached entry."""
    track_id: int
    preset: str
    chunk_idx: int
    tier: str
    access_count: int
    probability: float


class CacheContentsResponse(BaseModel):
    """Response model for cache contents."""
    l1_entries: List[CacheEntryInfo]
    l2_entries: List[CacheEntryInfo]
    l3_entries: List[CacheEntryInfo]
    total_entries: int


def create_cache_router(buffer_manager, broadcast_manager=None):
    """
    Create cache management router.

    Args:
        buffer_manager: MultiTierBufferManager instance
        broadcast_manager: Optional broadcast manager for notifications

    Returns:
        FastAPI router with cache endpoints
    """
    router = APIRouter(prefix="/cache", tags=["cache"])

    @router.get("/stats", response_model=CacheStatsResponse)
    async def get_cache_stats():
        """
        Get comprehensive cache statistics.

        Returns detailed statistics for all cache tiers including:
        - Size and utilization per tier
        - Hit rates per tier
        - Overall hit rate
        - Prediction accuracy
        - Session information
        """
        try:
            stats = buffer_manager.get_cache_stats()

            return CacheStatsResponse(
                l1=stats['l1'],
                l2=stats['l2'],
                l3=stats['l3'],
                overall=stats['overall'],
                prediction=stats['prediction']
            )

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/predictions", response_model=PredictionsResponse)
    async def get_predictions():
        """
        Get current preset predictions.

        Returns what presets the system predicts the user will switch to,
        along with confidence probabilities.
        """
        try:
            current_preset = buffer_manager.current_preset or "adaptive"
            current_position = buffer_manager.current_position

            # Get predictions
            predictions = buffer_manager.branch_predictor.predict_next_presets(
                current_preset,
                top_n=5
            )

            return PredictionsResponse(
                current_preset=current_preset,
                current_position=current_position,
                predictions=[
                    PresetPrediction(preset=preset, probability=prob)
                    for preset, prob in predictions
                ]
            )

        except Exception as e:
            logger.error(f"Failed to get predictions: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/contents", response_model=CacheContentsResponse)
    async def get_cache_contents():
        """
        Get detailed cache contents (for debugging/monitoring).

        Returns all cached entries across all tiers.
        """
        try:
            def tier_to_entries(tier, tier_name: str) -> List[CacheEntryInfo]:
                return [
                    CacheEntryInfo(
                        track_id=entry.track_id,
                        preset=entry.preset,
                        chunk_idx=entry.chunk_idx,
                        tier=tier_name,
                        access_count=entry.access_count,
                        probability=entry.probability
                    )
                    for entry in tier.entries.values()
                ]

            l1_entries = tier_to_entries(buffer_manager.l1_cache, "L1")
            l2_entries = tier_to_entries(buffer_manager.l2_cache, "L2")
            l3_entries = tier_to_entries(buffer_manager.l3_cache, "L3")

            return CacheContentsResponse(
                l1_entries=l1_entries,
                l2_entries=l2_entries,
                l3_entries=l3_entries,
                total_entries=len(l1_entries) + len(l2_entries) + len(l3_entries)
            )

        except Exception as e:
            logger.error(f"Failed to get cache contents: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/clear")
    async def clear_cache():
        """
        Clear all cache tiers.

        Useful for:
        - Freeing memory
        - Resetting predictions
        - Debugging
        """
        try:
            buffer_manager.clear_all_caches()

            logger.info("Cache cleared via API")

            # Broadcast cache cleared event
            if broadcast_manager:
                await broadcast_manager.broadcast({
                    "type": "cache_cleared",
                    "timestamp": buffer_manager.session_start
                })

            return {"status": "success", "message": "All caches cleared"}

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/clear/{tier}")
    async def clear_tier(tier: str):
        """
        Clear a specific cache tier.

        Args:
            tier: Tier to clear ("l1", "l2", or "l3")
        """
        try:
            tier_map = {
                "l1": buffer_manager.l1_cache,
                "l2": buffer_manager.l2_cache,
                "l3": buffer_manager.l3_cache
            }

            if tier.lower() not in tier_map:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tier: {tier}. Must be l1, l2, or l3"
                )

            tier_cache = tier_map[tier.lower()]
            tier_cache.clear()

            logger.info(f"{tier.upper()} cache cleared via API")

            # Broadcast tier cleared event
            if broadcast_manager:
                await broadcast_manager.broadcast({
                    "type": "cache_tier_cleared",
                    "tier": tier.upper()
                })

            return {"status": "success", "message": f"{tier.upper()} cache cleared"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to clear {tier} cache: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/check")
    async def check_chunk_cached(
        track_id: int,
        preset: str,
        chunk_idx: int,
        intensity: float = 1.0
    ):
        """
        Check if a specific chunk is cached.

        Useful for:
        - Debugging cache behavior
        - Verifying predictions
        - Testing cache integration
        """
        try:
            is_cached, tier = buffer_manager.is_chunk_cached(
                track_id, preset, chunk_idx, intensity
            )

            return {
                "track_id": track_id,
                "preset": preset,
                "chunk_idx": chunk_idx,
                "intensity": intensity,
                "is_cached": is_cached,
                "tier": tier,
                "estimated_latency_ms": 0 if tier == "L1" else (150 if tier == "L2" else (1000 if tier == "L3" else 3000))
            }

        except Exception as e:
            logger.error(f"Failed to check chunk: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/health")
    async def cache_health():
        """
        Get cache health status.

        Returns:
        - Whether cache is functioning
        - Current memory usage
        - Hit rate health (good/warning/critical)
        """
        try:
            stats = buffer_manager.get_cache_stats()

            # Determine health status based on hit rates
            l1_hit_rate = stats['l1']['hit_rate']
            overall_hit_rate = stats['overall']['overall_hit_rate']

            if l1_hit_rate >= 0.90 and overall_hit_rate >= 0.85:
                health_status = "healthy"
                health_message = "Cache performing optimally"
            elif l1_hit_rate >= 0.70 and overall_hit_rate >= 0.65:
                health_status = "warning"
                health_message = "Cache performance below target"
            else:
                health_status = "critical"
                health_message = "Cache performance poor - consider clearing or tuning"

            return {
                "status": health_status,
                "message": health_message,
                "l1_hit_rate": l1_hit_rate,
                "overall_hit_rate": overall_hit_rate,
                "total_memory_mb": stats['overall']['total_size_mb'],
                "memory_limit_mb": 99,
                "memory_utilization": stats['overall']['total_size_mb'] / 99,
                "prediction_accuracy": stats['prediction']['accuracy']
            }

        except Exception as e:
            logger.error(f"Failed to get cache health: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
