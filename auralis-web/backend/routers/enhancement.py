"""
Enhancement Router
~~~~~~~~~~~~~~~~~~

Handles real-time audio enhancement settings for the player.

Endpoints:
- POST /api/player/enhancement/toggle - Enable/disable enhancement
- POST /api/player/enhancement/preset - Change enhancement preset
- POST /api/player/enhancement/intensity - Adjust enhancement intensity
- GET /api/player/enhancement/status - Get current enhancement settings

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["enhancement"])

# Valid enhancement presets
VALID_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]


def create_enhancement_router(get_enhancement_settings, connection_manager, get_processing_cache=None, get_multi_tier_buffer=None, get_player_state_manager=None):
    """
    Factory function to create enhancement router with dependencies.

    Args:
        get_enhancement_settings: Callable that returns enhancement settings dict
        connection_manager: WebSocket connection manager for broadcasts
        get_processing_cache: Optional callable that returns processing cache dict
        get_multi_tier_buffer: Optional callable that returns MultiTierBufferManager
        get_player_state_manager: Optional callable that returns PlayerStateManager

    Returns:
        APIRouter: Configured router instance
    """

    @router.post("/api/player/enhancement/toggle")
    async def toggle_enhancement(enabled: bool):
        """
        Enable or disable real-time audio enhancement.

        Args:
            enabled: Boolean to enable/disable enhancement

        Returns:
            dict: Status message and current settings

        Raises:
            HTTPException: If toggling fails
        """
        try:
            enhancement_settings = get_enhancement_settings()
            enhancement_settings["enabled"] = enabled

            # Broadcast to all clients
            await connection_manager.broadcast({
                "type": "enhancement_toggled",
                "data": {
                    "enabled": enabled,
                    "preset": enhancement_settings["preset"],
                    "intensity": enhancement_settings["intensity"]
                }
            })

            logger.info(f"Enhancement {'enabled' if enabled else 'disabled'}")
            return {
                "message": f"Enhancement {'enabled' if enabled else 'disabled'}",
                "settings": enhancement_settings
            }
        except Exception as e:
            logger.error(f"Failed to toggle enhancement: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to toggle enhancement: {e}")

    @router.post("/api/player/enhancement/preset")
    async def set_enhancement_preset(preset: str):
        """
        Change the enhancement preset.

        Args:
            preset: Preset name (adaptive, gentle, warm, bright, punchy)

        Returns:
            dict: Status message and current settings

        Raises:
            HTTPException: If preset is invalid or change fails
        """
        if preset.lower() not in VALID_PRESETS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid preset. Must be one of: {', '.join(VALID_PRESETS)}"
            )

        try:
            enhancement_settings = get_enhancement_settings()
            old_preset = enhancement_settings.get("preset")
            enhancement_settings["preset"] = preset.lower()

            # Update multi-tier buffer manager for branch prediction learning
            if get_multi_tier_buffer and get_player_state_manager and old_preset != preset.lower():
                buffer_manager = get_multi_tier_buffer()
                player_state_manager = get_player_state_manager()
                if buffer_manager and player_state_manager:
                    state = player_state_manager.get_state()
                    # Only update if we have a current track
                    if state.current_track:
                        await buffer_manager.update_position(
                            track_id=state.current_track.id,
                            position=state.current_time,
                            preset=preset.lower(),
                            intensity=enhancement_settings["intensity"]
                        )
                        logger.info(f"🎯 Buffer manager learned preset switch: {old_preset} → {preset.lower()}")

            # Clear cache entries for tracks with the old preset to force reprocessing
            if get_processing_cache is not None and old_preset != preset.lower():
                cache = get_processing_cache()
                keys_to_remove = [k for k in cache.keys() if f"_{old_preset}_" in k]
                for key in keys_to_remove:
                    del cache[key]
                if keys_to_remove:
                    logger.info(f"🧹 Cleared {len(keys_to_remove)} cache entries for old preset '{old_preset}'")

            # Broadcast to all clients
            await connection_manager.broadcast({
                "type": "enhancement_preset_changed",
                "data": {
                    "preset": preset.lower(),
                    "enabled": enhancement_settings["enabled"],
                    "intensity": enhancement_settings["intensity"]
                }
            })

            logger.info(f"Enhancement preset changed to: {preset}")
            return {
                "message": f"Preset changed to {preset}",
                "settings": enhancement_settings
            }
        except Exception as e:
            logger.error(f"Failed to change preset: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to change preset: {e}")

    @router.post("/api/player/enhancement/intensity")
    async def set_enhancement_intensity(intensity: float):
        """
        Adjust the enhancement intensity.

        Args:
            intensity: Intensity value between 0.0 and 1.0

        Returns:
            dict: Status message and current settings

        Raises:
            HTTPException: If intensity is out of range or change fails
        """
        if not 0.0 <= intensity <= 1.0:
            raise HTTPException(
                status_code=400,
                detail="Intensity must be between 0.0 and 1.0"
            )

        try:
            enhancement_settings = get_enhancement_settings()
            old_intensity = enhancement_settings.get("intensity")
            enhancement_settings["intensity"] = intensity

            # Clear cache entries for tracks with the old intensity to force reprocessing
            if get_processing_cache is not None and old_intensity != intensity:
                cache = get_processing_cache()
                # Cache keys include intensity, so we need to clear all entries for current preset
                preset = enhancement_settings.get("preset", "adaptive")
                keys_to_remove = [k for k in cache.keys() if f"_{preset}_{old_intensity}_" in k]
                for key in keys_to_remove:
                    del cache[key]
                if keys_to_remove:
                    logger.info(f"🧹 Cleared {len(keys_to_remove)} cache entries for old intensity {old_intensity}")

            # Broadcast to all clients
            await connection_manager.broadcast({
                "type": "enhancement_intensity_changed",
                "data": {
                    "intensity": intensity,
                    "enabled": enhancement_settings["enabled"],
                    "preset": enhancement_settings["preset"]
                }
            })

            logger.info(f"Enhancement intensity changed to: {intensity}")
            return {
                "message": f"Intensity set to {intensity}",
                "settings": enhancement_settings
            }
        except Exception as e:
            logger.error(f"Failed to set intensity: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to set intensity: {e}")

    @router.get("/api/player/enhancement/status")
    async def get_enhancement_status():
        """
        Get current enhancement settings.

        Returns:
            dict: Current enhancement settings (enabled, preset, intensity)
        """
        return get_enhancement_settings()

    @router.post("/api/player/enhancement/cache/clear")
    async def clear_processing_cache():
        """
        Clear the processing cache (all cached enhanced audio files).
        Useful when testing or when cache becomes stale.

        Returns:
            dict: Status message with number of items cleared
        """
        if get_processing_cache is None:
            raise HTTPException(status_code=501, detail="Cache management not available")

        try:
            cache = get_processing_cache()
            cache_size = len(cache)
            cache.clear()

            logger.info(f"🧹 Processing cache cleared ({cache_size} items removed)")
            return {
                "message": "Processing cache cleared",
                "items_cleared": cache_size
            }
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to clear cache: {e}")

    return router
