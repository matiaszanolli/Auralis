"""
System Router - Health, Version, WebSocket

Infrastructure endpoints for system monitoring and real-time communication.
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


def create_system_router(
    manager,
    get_library_manager,
    get_processing_engine,
    HAS_AURALIS: bool
):
    """
    Create system router with dependencies.

    Args:
        manager: WebSocket ConnectionManager instance
        get_library_manager: Callable that returns LibraryManager instance
        get_processing_engine: Callable that returns ProcessingEngine instance
        HAS_AURALIS: Boolean indicating if Auralis is available
    """

    @router.get("/api/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "auralis_available": HAS_AURALIS,
            "library_manager": get_library_manager() is not None
        }

    @router.get("/api/version")
    async def get_version():
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
    async def websocket_endpoint(websocket: WebSocket):
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

                elif message.get("type") == "subscribe_job_progress":
                    # Subscribe to job progress updates
                    job_id = message.get("job_id")
                    processing_engine = get_processing_engine()
                    if job_id and processing_engine:
                        async def progress_callback(job_id, progress, message):
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
