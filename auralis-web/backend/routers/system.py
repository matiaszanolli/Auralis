"""
System Router - Health, Version, WebSocket

Infrastructure endpoints for system monitoring and real-time communication.
"""

import json
import logging
from typing import Callable, Optional, Any, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from audio_stream_controller import AudioStreamController

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


def create_system_router(
    manager: Any,
    get_processing_engine: Callable[..., Any],
    HAS_AURALIS: bool,
    get_player_manager: Optional[Callable[..., Any]] = None,
    get_state_manager: Optional[Callable[..., Any]] = None,
) -> APIRouter:
    """
    Create system router with dependencies.

    Args:
        manager: WebSocket ConnectionManager instance
        get_processing_engine: Callable that returns ProcessingEngine instance
        HAS_AURALIS: Boolean indicating if Auralis is available
        get_player_manager: Callable that returns PlayerManager instance
        get_state_manager: Callable that returns PlayerStateManager instance
    """

    @router.get("/api/health")
    async def health_check() -> Dict[str, Any]:
        """Health check endpoint"""
        return {
            "status": "healthy",
            "auralis_available": HAS_AURALIS
        }

    @router.get("/api/version")
    async def get_version() -> Dict[str, Any]:
        """
        Get version information.

        Returns detailed version info including:
        - version: Full semantic version
        - major, minor, patch: Version components
        - prerelease: Pre-release identifier (e.g., "beta.1")
        - build_date: Build date
        - api_version: API version for compatibility
        - db_schema_version: Database schema version
        - display: User-friendly version string
        """
        try:
            from auralis.version import get_version_info
            return get_version_info()
        except ImportError:
            logger.warning("auralis.version not available, using fallback")
            # Fallback if version module not available
            return {
                "version": "1.0.0-beta.1",
                "major": 1,
                "minor": 0,
                "patch": 0,
                "prerelease": "beta.1",
                "build": "",
                "build_date": "2025-10-24",
                "git_commit": "",
                "api_version": "v1",
                "db_schema_version": 3,
                "display": "Auralis v1.0.0-beta.1"
            }

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """
        WebSocket endpoint for real-time communication.

        Handles:
        - Ping/pong heartbeat
        - Processing settings updates
        - A/B comparison track loading
        - Job progress subscriptions
        """
        await manager.connect(websocket)
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle different message types
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

                elif message.get("type") == "processing_settings_update":
                    # Handle processing settings updates
                    settings = message.get("data", {})
                    logger.info(f"Processing settings updated: {settings}")

                    # Broadcast to all connected clients
                    await manager.broadcast({
                        "type": "processing_settings_applied",
                        "data": settings
                    })

                elif message.get("type") == "ab_track_loaded":
                    # Handle A/B comparison track loading
                    track_data = message.get("data", {})
                    logger.info(f"A/B track loaded: {track_data}")

                    # Broadcast to all connected clients
                    await manager.broadcast({
                        "type": "ab_track_ready",
                        "data": track_data
                    })

                elif message.get("type") == "play_enhanced":
                    # Handle enhanced audio playback request via WebSocket streaming
                    data = message.get("data", {})
                    track_id = data.get("track_id")
                    preset = data.get("preset", "adaptive")
                    intensity = data.get("intensity", 1.0)

                    logger.info(
                        f"Received play_enhanced: track_id={track_id}, "
                        f"preset={preset}, intensity={intensity}"
                    )

                    # Create audio stream controller and start streaming
                    try:
                        from chunked_processor import ChunkedAudioProcessor

                        controller = AudioStreamController(
                            chunked_processor_class=ChunkedAudioProcessor,
                            library_manager=get_library_manager(),
                        )

                        # Stream enhanced audio to client
                        await controller.stream_enhanced_audio(
                            track_id=track_id,
                            preset=preset,
                            intensity=intensity,
                            websocket=websocket,
                        )
                    except ImportError as e:
                        logger.error(f"ChunkedAudioProcessor not available: {e}")
                        await websocket.send_text(
                            json.dumps({
                                "type": "audio_stream_error",
                                "data": {
                                    "track_id": track_id,
                                    "error": "Audio processing not available",
                                    "code": "PROCESSOR_UNAVAILABLE"
                                }
                            })
                        )
                    except Exception as e:
                        logger.error(f"Error handling play_enhanced: {e}", exc_info=True)
                        await websocket.send_text(
                            json.dumps({
                                "type": "audio_stream_error",
                                "data": {
                                    "track_id": track_id,
                                    "error": str(e),
                                    "code": "STREAMING_ERROR"
                                }
                            })
                        )

                elif message.get("type") == "subscribe_job_progress":
                    # Subscribe to job progress updates
                    job_id = message.get("job_id")
                    processing_engine = get_processing_engine()
                    if job_id and processing_engine:
                        async def progress_callback(job_id: str, progress: float, message: str) -> None:
                            await websocket.send_text(json.dumps({
                                "type": "job_progress",
                                "data": {
                                    "job_id": job_id,
                                    "progress": progress,
                                    "message": message
                                }
                            }))

                        processing_engine.register_progress_callback(job_id, progress_callback)

        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return router
