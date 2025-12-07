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
import asyncio
import os

logger = logging.getLogger(__name__)
router = APIRouter(tags=["enhancement"])

# Valid enhancement presets
VALID_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]

# Chunk configuration (must match chunked_processor.py)
# NEW (Beta.9): Reduced from 30s → 10s for instant toggle feel
CHUNK_DURATION = 10  # seconds per chunk (reduced from 30s for Phase 2)


def create_enhancement_router(get_enhancement_settings, connection_manager, get_processing_cache=None, get_multi_tier_buffer=None, get_player_state_manager=None, get_processing_engine=None):
    """
    Factory function to create enhancement router with dependencies.

    Args:
        get_enhancement_settings: Callable that returns enhancement settings dict
        connection_manager: WebSocket connection manager for broadcasts
        get_processing_cache: Optional callable that returns processing cache dict
        get_player_state_manager: Optional callable that returns PlayerStateManager
        get_processing_engine: Optional callable that returns ProcessingEngine

    Returns:
        APIRouter: Configured router instance
    """

    async def _preprocess_upcoming_chunks(track_id: int, filepath: str, current_time: float, preset: str, intensity: float):
        """
        Background task to pre-process upcoming chunks when enhancement is enabled mid-playback.
        This prevents audio stopping while waiting for on-demand processing.

        Args:
            track_id: Track database ID
            filepath: Path to audio file
            current_time: Current playback position in seconds
            preset: Enhancement preset name
            intensity: Enhancement intensity (0.0-1.0)
        """
        try:
            # Import here to avoid circular dependencies
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from chunked_processor import ChunkedAudioProcessor
            import soundfile as sf

            # Calculate current chunk and next 3 chunks to pre-process
            current_chunk_idx = int(current_time / CHUNK_DURATION)
            chunks_to_process = [current_chunk_idx + i for i in range(1, 4)]  # Next 3 chunks

            logger.info(f"🎯 Pre-processing chunks {chunks_to_process} for track {track_id} (current chunk: {current_chunk_idx})")

            # Get audio duration to avoid processing non-existent chunks
            info = sf.info(filepath)
            total_duration = info.duration
            total_chunks = int(total_duration / CHUNK_DURATION) + 1

            # Create processor
            processor = ChunkedAudioProcessor(
                track_id=track_id,
                filepath=filepath,
                preset=preset,
                intensity=intensity,
                chunk_cache={}
            )

            # Process each chunk
            processed_count = 0
            for chunk_idx in chunks_to_process:
                if chunk_idx >= total_chunks:
                    break  # Don't process chunks beyond the track

                try:
                    # Process chunk (this will cache the WAV file)
                    wav_chunk_path = processor.get_wav_chunk_path(chunk_idx)

                    if os.path.exists(wav_chunk_path):
                        processed_count += 1
                        logger.info(f"✅ Pre-processed chunk {chunk_idx} ({processed_count}/{len(chunks_to_process)})")
                    else:
                        logger.warning(f"⚠️ Pre-processing failed for chunk {chunk_idx}: output file not found")

                except Exception as e:
                    logger.error(f"❌ Pre-processing failed for chunk {chunk_idx}: {e}")
                    continue

            logger.info(f"🎯 Pre-processing complete: {processed_count} chunks ready")

        except Exception as e:
            logger.error(f"❌ Background chunk pre-processing failed: {e}")

    @router.post("/api/player/enhancement/toggle")
    async def toggle_enhancement(enabled: bool):
        """
        Enable or disable real-time audio enhancement.

        When enabling mid-playback, automatically pre-processes upcoming chunks
        in the background to prevent audio stopping.

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

            # If enabling enhancement mid-playback, pre-process upcoming chunks in background
            if enabled and get_player_state_manager is not None:
                player_state_manager = get_player_state_manager()
                if player_state_manager:
                    state = player_state_manager.get_state()
                    # Only pre-process if actively playing
                    if state.current_track and state.state.value == "playing":
                        # Launch background task to pre-process next 3 chunks
                        asyncio.create_task(_preprocess_upcoming_chunks(
                            track_id=state.current_track.id,
                            filepath=state.current_track.file_path,
                            current_time=state.current_time,
                            preset=enhancement_settings.get("preset", "adaptive"),
                            intensity=enhancement_settings.get("intensity", 1.0)
                        ))
                        logger.info(f"🎯 Launched background pre-processing for track {state.current_track.id} at {state.current_time:.1f}s")

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

            # NOTE: We keep the old preset cached for instant toggling back
            # Proactive buffering will handle caching the new preset in background
            # This prevents the 2-5s delay when switching presets
            logger.info(f"⚡ Preset switched instantly: {old_preset} → {preset.lower()} (cache preserved)")

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

    @router.get("/api/player/mastering/recommendation/{track_id}")
    async def get_mastering_recommendation(track_id: int, filepath: str = None, confidence_threshold: float = 0.4):
        """
        Get weighted mastering profile recommendation for a track (Priority 4).

        Analyzes the track's audio characteristics and returns single or blended
        profile recommendations based on confidence thresholds.

        Args:
            track_id: Track database ID
            filepath: Path to audio file (required for analysis)
            confidence_threshold: Threshold for switching from single to blended recommendations (0.0-1.0)

        Returns:
            dict: MasteringRecommendation serialized to JSON with weighted_profiles if hybrid
                {
                    "primary_profile_id": "...",
                    "primary_profile_name": "...",
                    "confidence_score": 0.73,
                    "predicted_loudness_change": -0.93,
                    "predicted_crest_change": 1.4,
                    "predicted_centroid_change": 100.0,
                    "weighted_profiles": [  // Only present if hybrid recommendation
                        {"profile_id": "...", "profile_name": "...", "weight": 0.43},
                        ...
                    ],
                    "reasoning": "..."
                }

        Raises:
            HTTPException: 400 if filepath not provided or track not found
            HTTPException: 500 if analysis fails
        """
        if not filepath:
            raise HTTPException(status_code=400, detail="filepath parameter required")

        try:
            import os
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from chunked_processor import ChunkedAudioProcessor

            # Create processor (caches the recommendation internally)
            processor = ChunkedAudioProcessor(
                track_id=track_id,
                filepath=filepath,
                preset=None,  # No processing needed for analysis only
                intensity=1.0,
                chunk_cache={}
            )

            # Get weighted recommendation
            rec = processor.get_mastering_recommendation(confidence_threshold=confidence_threshold)

            if rec is None:
                raise HTTPException(status_code=500, detail="Failed to analyze audio file")

            # Return serialized recommendation
            return rec.to_dict()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to generate mastering recommendation for track {track_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    @router.get("/api/processing/parameters")
    async def get_processing_parameters():
        """
        Get current processing parameters from the continuous space system.
        This shows what the auto-mastering engine is doing in real-time.

        Reads from the global content profile cache populated by ChunkedAudioProcessor
        during streaming playback.

        Returns:
            dict: Processing parameters including coordinates, targets, and adjustments
        """
        try:
            # Import the helper function from chunked_processor
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from chunked_processor import get_last_content_profile

            # Get current preset
            preset = get_enhancement_settings().get("preset", "adaptive")

            # Try to get profile from ChunkedAudioProcessor global cache
            profile = get_last_content_profile(preset)

            if profile is None:
                # No processing data yet - return default values
                logger.debug(f"No processing profile found for preset '{preset}' - returning defaults")
                return {
                    "spectral_balance": 0.5,
                    "dynamic_range": 0.5,
                    "energy_level": 0.5,
                    "target_lufs": -14.0,
                    "peak_target_db": -1.0,
                    "bass_boost": 0.0,
                    "air_boost": 0.0,
                    "compression_amount": 0.0,
                    "expansion_amount": 0.0,
                    "stereo_width": 0.75
                }

            # Extract coordinates (ProcessingCoordinates dataclass or dict)
            coords = profile.get('coordinates')
            params = profile.get('parameters')

            if coords is None or params is None:
                # Legacy mode or no continuous space data
                logger.debug(f"Profile for preset '{preset}' missing coordinates or parameters")
                return {
                    "spectral_balance": 0.5,
                    "dynamic_range": 0.5,
                    "energy_level": 0.5,
                    "target_lufs": -14.0,
                    "peak_target_db": -1.0,
                    "bass_boost": 0.0,
                    "air_boost": 0.0,
                    "compression_amount": 0.0,
                    "expansion_amount": 0.0,
                    "stereo_width": 0.75
                }

            # Extract values (handle both dataclass and dict formats)
            def get_attr(obj, attr, default=0.0):
                """Get attribute from dataclass or dict"""
                if isinstance(obj, dict):
                    return obj.get(attr, default)
                return getattr(obj, attr, default)

            # Convert ProcessingCoordinates and ProcessingParameters to dict
            result = {
                "spectral_balance": get_attr(coords, 'spectral_balance', 0.5),
                "dynamic_range": get_attr(coords, 'dynamic_range', 0.5),
                "energy_level": get_attr(coords, 'energy_level', 0.5),
                "target_lufs": get_attr(params, 'target_lufs', -14.0),
                "peak_target_db": get_attr(params, 'peak_target_db', -1.0),
                "bass_boost": get_attr(params, 'eq_curve', {}).get('low_shelf_gain', 0.0),
                "air_boost": get_attr(params, 'eq_curve', {}).get('high_shelf_gain', 0.0),
                "compression_amount": get_attr(params, 'compression_params', {}).get('amount', 0.0),
                "expansion_amount": get_attr(params, 'expansion_params', {}).get('amount', 0.0),
                "stereo_width": get_attr(params, 'stereo_width_target', 0.75)
            }

            logger.debug(f"📊 Returning processing parameters for preset '{preset}': {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to get processing parameters: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return default values on error
            return {
                "spectral_balance": 0.5,
                "dynamic_range": 0.5,
                "energy_level": 0.5,
                "target_lufs": -14.0,
                "peak_target_db": -1.0,
                "bass_boost": 0.0,
                "air_boost": 0.0,
                "compression_amount": 0.0,
                "expansion_amount": 0.0,
                "stereo_width": 0.75
            }

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
