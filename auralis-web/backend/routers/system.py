"""
System Router - Health, Version, WebSocket

Infrastructure endpoints for system monitoring and real-time communication.
"""

import asyncio
import json
import logging
from typing import Any
from collections.abc import Callable

from audio_stream_controller import AudioStreamController
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websocket_security import (
    WebSocketRateLimiter,
    validate_and_parse_message,
    send_error_response,
)

logger = logging.getLogger(__name__)

# Track active streaming tasks per WebSocket to allow cancellation
_active_streaming_tasks: dict[int, asyncio.Task] = {}
_active_streaming_tasks_lock = asyncio.Lock()  # Protects all _active_streaming_tasks access (fixes #2425)

# Global rate limiter for all WebSocket connections (fixes #2156)
_rate_limiter = WebSocketRateLimiter(max_messages_per_second=10)

router = APIRouter(tags=["system"])


def create_system_router(
    manager: Any,
    get_processing_engine: Callable[..., Any],
    HAS_AURALIS: bool,
    get_repository_factory: Callable[..., Any] | None = None,
    get_player_manager: Callable[..., Any] | None = None,
    get_state_manager: Callable[..., Any] | None = None,
    get_enhancement_settings: Callable[[], dict[str, Any]] | None = None,
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
        get_enhancement_settings: Optional callable that returns enhancement settings dict
    """

    @router.get("/api/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint"""
        return {
            "status": "healthy",
            "auralis_available": HAS_AURALIS
        }

    @router.get("/api/version")
    async def get_version() -> dict[str, Any]:
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
            # Fallback when auralis.version cannot be imported (broken install, path issue).
            # Keep in sync with auralis/version.py — the single source of truth (fixes #2335).
            return {
                "version": "1.2.1-beta.1",
                "major": 1,
                "minor": 2,
                "patch": 1,
                "prerelease": "beta.1",
                "build": "",
                "build_date": "2026-02-20",
                "git_commit": "",
                "api_version": "v1",
                "db_schema_version": 3,
                "display": "Auralis v1.2.1-beta.1"
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

                # Security: Check rate limit (fixes #2156)
                allowed, error_msg = _rate_limiter.check_rate_limit(websocket)
                if not allowed:
                    logger.warning(f"Rate limit exceeded for WebSocket {id(websocket)}: {error_msg}")
                    await send_error_response(websocket, "rate_limit_exceeded", error_msg)
                    continue

                # Security: Validate message size and structure (fixes #2156)
                message, error = await validate_and_parse_message(data, websocket)
                if error or not message:
                    # Error already sent to client by validate_and_parse_message
                    continue

                # Handle different message types
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

                elif message.get("type") == "heartbeat":
                    # Keepalive sent by RealTimeAnalysisStream every 30s — no response needed
                    pass

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

                    # Validate track_id before launching any background task (#2393)
                    if not isinstance(track_id, int) or track_id <= 0:
                        logger.warning(f"Invalid track_id in play_enhanced: {track_id!r}")
                        await send_error_response(
                            websocket,
                            "invalid_track_id",
                            "track_id must be a positive integer"
                        )
                        continue

                    # Use stored enhancement settings as source of truth (fixes #2103)
                    # This ensures REST API changes are respected
                    enhancement_enabled = True
                    preset = "adaptive"
                    intensity = 1.0

                    if get_enhancement_settings is not None:
                        settings = get_enhancement_settings()
                        enhancement_enabled = settings.get("enabled", True)
                        preset = settings.get("preset", "adaptive")
                        intensity = settings.get("intensity", 1.0)
                        logger.info(
                            f"Using stored enhancement settings: enabled={enhancement_enabled}, "
                            f"preset={preset}, intensity={intensity}"
                        )
                    else:
                        # Fallback to message data if settings not available
                        # Validate preset (fixes #2112)
                        VALID_PRESETS = ["adaptive", "gentle", "warm", "bright", "punchy"]
                        preset = data.get("preset", "adaptive").lower()
                        if preset not in VALID_PRESETS:
                            logger.warning(f"Invalid preset '{preset}' in play_enhanced, using 'adaptive'")
                            await send_error_response(
                                websocket,
                                "invalid_preset",
                                f"Invalid preset '{preset}'. Must be one of: {', '.join(VALID_PRESETS)}"
                            )
                            continue

                        # Validate intensity (fixes #2112)
                        intensity = data.get("intensity", 1.0)
                        if not isinstance(intensity, (int, float)) or not (0.0 <= intensity <= 1.0):
                            logger.warning(f"Invalid intensity '{intensity}' in play_enhanced, clamping to 0.0-1.0")
                            intensity = max(0.0, min(1.0, float(intensity))) if isinstance(intensity, (int, float)) else 1.0

                        logger.warning("Enhancement settings not available, using validated message data")

                    logger.info(
                        f"Received play_enhanced: track_id={track_id}, "
                        f"preset={preset}, intensity={intensity}"
                    )

                    if not enhancement_enabled:
                        # Enhancement is disabled - send error message to client
                        logger.warning(f"Enhancement disabled, rejecting play_enhanced request for track {track_id}")
                        try:
                            await websocket.send_text(
                                json.dumps({
                                    "type": "audio_stream_error",
                                    "data": {
                                        "track_id": track_id,
                                        "error": "Auto-mastering is currently disabled. Enable it in the enhancement panel to use this feature.",
                                        "code": "ENHANCEMENT_DISABLED",
                                        "stream_type": "enhanced",
                                    }
                                })
                            )
                        except Exception as e:
                            logger.error(f"Failed to send enhancement disabled error: {e}")
                        continue  # Skip to next message

                    ws_id = id(websocket)

                    # Define streaming coroutine
                    async def stream_audio():
                        # Capture task identity to prevent orphaned task race (fixes #2164)
                        my_task = asyncio.current_task()
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
                                            "code": "PROCESSOR_UNAVAILABLE",
                                            "stream_type": "enhanced",
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
                                            "code": "STREAMING_ERROR",
                                            "stream_type": "enhanced",
                                        }
                                    })
                                )
                            except Exception:
                                pass  # WebSocket may be closed
                        finally:
                            # Idempotent self-cleanup under lock (fixes #2425)
                            async with _active_streaming_tasks_lock:
                                if _active_streaming_tasks.get(ws_id) is my_task:
                                    _active_streaming_tasks.pop(ws_id, None)

                    # Atomically: clean up done tasks, cancel prior stream, register new task (fixes #2425, #2430)
                    async with _active_streaming_tasks_lock:
                        for k in [k for k, v in _active_streaming_tasks.items() if v.done()]:
                            _active_streaming_tasks.pop(k, None)
                        old_task = _active_streaming_tasks.pop(ws_id, None)
                        if old_task and not old_task.done():
                            logger.info(f"Cancelling existing streaming task for ws {ws_id}")
                            old_task.cancel()
                        task = asyncio.create_task(stream_audio())
                        _active_streaming_tasks[ws_id] = task
                    logger.info(f"Started background streaming task for track {track_id}")

                elif message.get("type") == "play_normal":
                    # Handle normal (unprocessed) audio playback for comparison
                    data = message.get("data", {})
                    track_id = data.get("track_id")

                    # Validate track_id before launching any background task (#2393)
                    if not isinstance(track_id, int) or track_id <= 0:
                        logger.warning(f"Invalid track_id in play_normal: {track_id!r}")
                        await send_error_response(
                            websocket,
                            "invalid_track_id",
                            "track_id must be a positive integer"
                        )
                        continue

                    logger.info(f"Received play_normal: track_id={track_id}")

                    ws_id = id(websocket)

                    # Define streaming coroutine
                    async def stream_normal():
                        # Capture task identity to prevent orphaned task race (fixes #2164)
                        my_task = asyncio.current_task()
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
                                            "code": "STREAMING_ERROR",
                                            "stream_type": "normal",
                                        }
                                    })
                                )
                            except Exception:
                                pass  # WebSocket may be closed
                        finally:
                            # Idempotent self-cleanup under lock (fixes #2425)
                            async with _active_streaming_tasks_lock:
                                if _active_streaming_tasks.get(ws_id) is my_task:
                                    _active_streaming_tasks.pop(ws_id, None)

                    # Atomically: clean up done tasks, cancel prior stream, register new task (fixes #2425, #2430)
                    async with _active_streaming_tasks_lock:
                        for k in [k for k, v in _active_streaming_tasks.items() if v.done()]:
                            _active_streaming_tasks.pop(k, None)
                        old_task = _active_streaming_tasks.pop(ws_id, None)
                        if old_task and not old_task.done():
                            logger.info(f"Cancelling existing streaming task for ws {ws_id}")
                            old_task.cancel()
                        task = asyncio.create_task(stream_normal())
                        _active_streaming_tasks[ws_id] = task
                    logger.info(f"Started background normal streaming task for track {track_id}")

                elif message.get("type") == "pause":
                    # Pause audio playback
                    logger.info("Received pause command via WebSocket")

                    # Cancel active streaming task if any (fixes #2425 — idempotent pop under lock)
                    ws_id = id(websocket)
                    async with _active_streaming_tasks_lock:
                        task = _active_streaming_tasks.pop(ws_id, None)
                    if task and not task.done():
                        task.cancel()
                        logger.info("Cancelled active streaming task")

                    # Broadcast pause state to client
                    await websocket.send_text(json.dumps({
                        "type": "playback_paused",
                        "data": {
                            "success": True
                        }
                    }))

                elif message.get("type") == "stop":
                    # Stop audio playback
                    logger.info("Received stop command via WebSocket")

                    # Cancel active streaming task if any (fixes #2425 — idempotent pop under lock)
                    ws_id = id(websocket)
                    async with _active_streaming_tasks_lock:
                        task = _active_streaming_tasks.pop(ws_id, None)
                    if task and not task.done():
                        task.cancel()
                        logger.info("Cancelled active streaming task")

                    # Broadcast stop state to client
                    await websocket.send_text(json.dumps({
                        "type": "playback_stopped",
                        "data": {
                            "success": True
                        }
                    }))

                elif message.get("type") == "seek":
                    # Seek to a specific position in the track
                    # This restarts streaming from the chunk containing the target position
                    data = message.get("data", {})
                    track_id = data.get("track_id")
                    position = data.get("position", 0)  # Position in seconds

                    # Validate track_id and position before launching any background task (#2393)
                    if not isinstance(track_id, int) or track_id <= 0:
                        logger.warning(f"Invalid track_id in seek: {track_id!r}")
                        await send_error_response(
                            websocket,
                            "invalid_track_id",
                            "track_id must be a positive integer"
                        )
                        continue

                    if not isinstance(position, (int, float)) or position < 0:
                        logger.warning(f"Invalid seek position: {position!r}")
                        await send_error_response(
                            websocket,
                            "invalid_seek_position",
                            "position must be a non-negative number"
                        )
                        continue

                    # Use stored enhancement settings (fixes #2103)
                    preset = "adaptive"
                    intensity = 1.0
                    if get_enhancement_settings is not None:
                        settings = get_enhancement_settings()
                        preset = settings.get("preset", "adaptive")
                        intensity = settings.get("intensity", 1.0)

                    logger.info(
                        f"Received seek: track_id={track_id}, "
                        f"position={position}s, preset={preset}"
                    )

                    # Pop prior task under lock; cancel and await outside lock to avoid deadlock (fixes #2425, #2430)
                    ws_id = id(websocket)
                    async with _active_streaming_tasks_lock:
                        for k in [k for k, v in _active_streaming_tasks.items() if v.done()]:
                            _active_streaming_tasks.pop(k, None)
                        old_task = _active_streaming_tasks.pop(ws_id, None)
                    if old_task and not old_task.done():
                        logger.info("Cancelling existing streaming task for seek")
                        old_task.cancel()
                        try:
                            await asyncio.wait_for(asyncio.shield(old_task), timeout=0.1)
                        except (asyncio.CancelledError, TimeoutError):
                            pass

                    # Send seek_started acknowledgment to client
                    await websocket.send_text(json.dumps({
                        "type": "seek_started",
                        "data": {
                            "track_id": track_id,
                            "position": position,
                        }
                    }))

                    # Define streaming coroutine with seek position
                    async def stream_from_position():
                        # Capture task identity to prevent orphaned task race (fixes #2164)
                        my_task = asyncio.current_task()
                        try:
                            from chunked_processor import ChunkedAudioProcessor

                            controller = AudioStreamController(
                                chunked_processor_class=ChunkedAudioProcessor,
                                get_repository_factory=get_repository_factory,
                            )

                            await controller.stream_enhanced_audio_from_position(
                                track_id=track_id,
                                preset=preset,
                                intensity=intensity,
                                websocket=websocket,
                                start_position=position,
                            )
                        except asyncio.CancelledError:
                            logger.info(f"Seek streaming task cancelled for track {track_id}")
                        except Exception as e:
                            logger.error(f"Error in seek streaming task: {e}", exc_info=True)
                            try:
                                await websocket.send_text(
                                    json.dumps({
                                        "type": "audio_stream_error",
                                        "data": {
                                            "track_id": track_id,
                                            "error": str(e),
                                            "code": "SEEK_ERROR",
                                            "stream_type": "enhanced",
                                        }
                                    })
                                )
                            except Exception:
                                pass
                        finally:
                            # Idempotent self-cleanup under lock (fixes #2425)
                            async with _active_streaming_tasks_lock:
                                if _active_streaming_tasks.get(ws_id) is my_task:
                                    _active_streaming_tasks.pop(ws_id, None)

                    # Register new seek task under lock (fixes #2425)
                    async with _active_streaming_tasks_lock:
                        task = asyncio.create_task(stream_from_position())
                        _active_streaming_tasks[ws_id] = task
                    logger.info(f"Started seek streaming task for track {track_id} at {position}s")

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

                else:
                    # Unknown message type (fixes #2417)
                    message_type = message.get("type", "unknown")
                    logger.warning(f"Unknown WebSocket message type: {message_type!r}")
                    await send_error_response(websocket, "unknown_message_type", f"Unknown message type: {message_type}")

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

            # Cancel any active streaming task — idempotent pop under lock (fixes #2425)
            async with _active_streaming_tasks_lock:
                task = _active_streaming_tasks.pop(ws_id, None)
            if task and not task.done():
                logger.info(f"Cancelling streaming task on disconnect for ws {ws_id}")
                task.cancel()

            # Clean up rate limiter (fixes #2156)
            _rate_limiter.cleanup(websocket)

            # Remove from connection manager
            manager.disconnect(websocket)

    return router
