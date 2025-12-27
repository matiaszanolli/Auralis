"""
System Router - Health, Version, WebSocket

Infrastructure endpoints for system monitoring and real-time communication.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

from audio_stream_controller import AudioStreamController
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Track active streaming tasks per WebSocket to allow cancellation
_active_streaming_tasks: Dict[int, asyncio.Task] = {}

router = APIRouter(tags=["system"])


def create_system_router(
    manager: Any,
    get_processing_engine: Callable[..., Any],
    HAS_AURALIS: bool,
    get_repository_factory: Optional[Callable[..., Any]] = None,
    get_player_manager: Optional[Callable[..., Any]] = None,
    get_state_manager: Optional[Callable[..., Any]] = None,
) -> APIRouter:
    """
    Create system router with dependencies.

    Args:
        manager: WebSocket ConnectionManager instance
        get_processing_engine: Callable that returns ProcessingEngine instance
        HAS_AURALIS: Boolean indicating if Auralis is available
        get_repository_factory: Optional callable that returns RepositoryFactory instance
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

                    # Cancel any existing streaming task for this websocket
                    ws_id = id(websocket)
                    if ws_id in _active_streaming_tasks:
                        old_task = _active_streaming_tasks[ws_id]
                        if not old_task.done():
                            logger.info(f"Cancelling existing streaming task for ws {ws_id}")
                            old_task.cancel()

                    # Define streaming coroutine
                    async def stream_audio():
                        try:
                            from chunked_processor import ChunkedAudioProcessor

                            controller = AudioStreamController(
                                chunked_processor_class=ChunkedAudioProcessor,
                                get_repository_factory=get_repository_factory,
                            )

                            if controller.fingerprint_generator:
                                logger.info("✅ FingerprintGenerator available - on-demand fingerprint generation enabled")
                            else:
                                logger.warning("⚠️  FingerprintGenerator not available - using database/cached fingerprints only")

                            await controller.stream_enhanced_audio(
                                track_id=track_id,
                                preset=preset,
                                intensity=intensity,
                                websocket=websocket,
                            )
                        except asyncio.CancelledError:
                            logger.info(f"Streaming task cancelled for track {track_id}")
                        except ImportError as e:
                            logger.error(f"ChunkedAudioProcessor not available: {e}")
                            try:
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
                            except Exception:
                                pass  # WebSocket may be closed
                        except Exception as e:
                            logger.error(f"Error in streaming task: {e}", exc_info=True)
                            try:
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
                            except Exception:
                                pass  # WebSocket may be closed
                        finally:
                            # Clean up task reference
                            if ws_id in _active_streaming_tasks:
                                del _active_streaming_tasks[ws_id]

                    # Start streaming in background task (non-blocking)
                    # This allows the message loop to continue processing ping/pong
                    task = asyncio.create_task(stream_audio())
                    _active_streaming_tasks[ws_id] = task
                    logger.info(f"Started background streaming task for track {track_id}")

                elif message.get("type") == "play_normal":
                    # Handle normal (unprocessed) audio playback for comparison
                    data = message.get("data", {})
                    track_id = data.get("track_id")

                    logger.info(f"Received play_normal: track_id={track_id}")

                    # Cancel any existing streaming task for this websocket
                    ws_id = id(websocket)
                    if ws_id in _active_streaming_tasks:
                        old_task = _active_streaming_tasks[ws_id]
                        if not old_task.done():
                            logger.info(f"Cancelling existing streaming task for ws {ws_id}")
                            old_task.cancel()

                    # Define streaming coroutine
                    async def stream_normal():
                        try:
                            controller = AudioStreamController(
                                chunked_processor_class=None,
                                get_repository_factory=get_repository_factory,
                            )

                            # Stream original audio to client (no DSP processing)
                            await controller.stream_normal_audio(
                                track_id=track_id,
                                websocket=websocket,
                            )
                        except asyncio.CancelledError:
                            logger.info(f"Normal streaming task cancelled for track {track_id}")
                        except Exception as e:
                            logger.error(f"Error in normal streaming task: {e}", exc_info=True)
                            try:
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
                            except Exception:
                                pass  # WebSocket may be closed
                        finally:
                            # Clean up task reference
                            if ws_id in _active_streaming_tasks:
                                del _active_streaming_tasks[ws_id]

                    # Start streaming in background task (non-blocking)
                    task = asyncio.create_task(stream_normal())
                    _active_streaming_tasks[ws_id] = task
                    logger.info(f"Started background normal streaming task for track {track_id}")

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
            logger.info("WebSocket client disconnected normally")
        except RuntimeError as e:
            # Handle "WebSocket is not connected" and similar errors
            logger.warning(f"WebSocket runtime error: {e}")
        except Exception as e:
            logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
        finally:
            # Always clean up on disconnect
            ws_id = id(websocket)

            # Cancel any active streaming task for this websocket
            if ws_id in _active_streaming_tasks:
                task = _active_streaming_tasks[ws_id]
                if not task.done():
                    logger.info(f"Cancelling streaming task on disconnect for ws {ws_id}")
                    task.cancel()
                del _active_streaming_tasks[ws_id]

            # Remove from connection manager
            manager.disconnect(websocket)

    return router
