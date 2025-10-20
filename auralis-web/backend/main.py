#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auralis Web Backend
~~~~~~~~~~~~~~~~~~

Modern FastAPI backend for Auralis audio processing and library management.
Replaces the Tkinter GUI with a professional web interface.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio
import json
import sys
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

# Add parent directory to path for Auralis imports
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from auralis.library import LibraryManager
    from auralis.library.scanner import LibraryScanner
    from auralis.player.enhanced_audio_player import EnhancedAudioPlayer, PlaybackState
    from auralis.player.config import PlayerConfig
    from auralis.core.config import Config
    HAS_AURALIS = True
except ImportError as e:
    print(f"⚠️  Auralis library not available: {e}")
    HAS_AURALIS = False

# Import processing components
try:
    from processing_engine import ProcessingEngine
    from processing_api import router as processing_router, set_processing_engine
    HAS_PROCESSING = True
except ImportError as e:
    print(f"⚠️  Processing components not available: {e}")
    HAS_PROCESSING = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Auralis Web API",
    description="Modern web backend for Auralis audio processing",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include processing API routes
if HAS_PROCESSING:
    app.include_router(processing_router)

# Global state
library_manager: Optional[LibraryManager] = None
audio_player: Optional[EnhancedAudioPlayer] = None
if HAS_PROCESSING:
    processing_engine: Optional[ProcessingEngine] = None
else:
    processing_engine = None
connected_websockets: List[WebSocket] = []

# Initialize Auralis components
@app.on_event("startup")
async def startup_event():
    """Initialize Auralis components on startup"""
    global library_manager, audio_player, processing_engine

    if HAS_AURALIS:
        try:
            library_manager = LibraryManager()
            logger.info("✅ Auralis LibraryManager initialized")

            # Initialize enhanced audio player with optimized config
            player_config = PlayerConfig(
                buffer_size=1024,
                sample_rate=44100,
                enable_level_matching=True,
                enable_frequency_matching=False,
                enable_stereo_width=False,
                enable_auto_mastering=False,
                enable_advanced_smoothing=True,
                max_db_change_per_second=2.0
            )
            audio_player = EnhancedAudioPlayer(player_config)
            logger.info("✅ Enhanced Audio Player initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Auralis components: {e}")
    else:
        logger.warning("⚠️  Auralis not available - running in demo mode")

    # Initialize processing engine
    if HAS_PROCESSING:
        try:
            processing_engine = ProcessingEngine(max_concurrent_jobs=2)
            set_processing_engine(processing_engine)
            # Start the processing worker
            asyncio.create_task(processing_engine.start_worker())
            logger.info("✅ Processing Engine initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Processing Engine: {e}")
    else:
        logger.warning("⚠️  Processing engine not available")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")

manager = ConnectionManager()

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
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

# API Routes

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "auralis_available": HAS_AURALIS,
        "library_manager": library_manager is not None
    }

@app.get("/api/version")
async def get_version():
    """Get version information"""
    try:
        from version import get_version_info
        return get_version_info()
    except ImportError:
        # Fallback if version module not available
        return {
            "api_version": "1.0.0",
            "api_version_info": {"major": 1, "minor": 0, "patch": 0},
            "db_schema_version": 1,
            "min_client_version": "1.0.0"
        }

@app.get("/api/library/stats")
async def get_library_stats():
    """Get library statistics"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        stats = library_manager.get_library_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")

@app.get("/api/library/tracks")
async def get_tracks(limit: int = 50, offset: int = 0, search: Optional[str] = None):
    """Get tracks from library"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        if search:
            tracks = library_manager.search_tracks(search, limit=limit)
        else:
            tracks = library_manager.get_recent_tracks(limit=limit)

        # Convert to dicts for JSON serialization
        tracks_data = []
        for track in tracks:
            if hasattr(track, 'to_dict'):
                tracks_data.append(track.to_dict())
            else:
                tracks_data.append({
                    'id': getattr(track, 'id', None),
                    'title': getattr(track, 'title', 'Unknown'),
                    'filepath': getattr(track, 'filepath', ''),
                    'duration': getattr(track, 'duration', 0),
                    'format': getattr(track, 'format', 'Unknown')
                })

        return {
            "tracks": tracks_data,
            "total": len(tracks_data),
            "offset": offset,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tracks: {e}")

@app.get("/api/library/artists")
async def get_artists():
    """Get all artists"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        # This would need to be implemented in the library manager
        return {"artists": [], "message": "Artist listing not yet implemented"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get artists: {e}")

@app.post("/api/library/scan")
async def scan_directory(directory: str):
    """Scan directory for audio files"""
    if not library_manager:
        raise HTTPException(status_code=503, detail="Library manager not available")

    try:
        scanner = LibraryScanner(library_manager)

        # Start scan in background
        async def scan_worker():
            try:
                result = scanner.scan_single_directory(directory, recursive=True)

                # Broadcast scan completion to all connected clients
                await manager.broadcast({
                    "type": "scan_complete",
                    "data": {
                        "directory": directory,
                        "files_found": result.files_found,
                        "files_added": result.files_added,
                        "files_updated": result.files_updated,
                        "files_failed": result.files_failed,
                        "scan_time": result.scan_time
                    }
                })

            except Exception as e:
                await manager.broadcast({
                    "type": "scan_error",
                    "data": {"directory": directory, "error": str(e)}
                })

        # Start the scan
        asyncio.create_task(scan_worker())

        return {"message": f"Scan of {directory} started", "status": "scanning"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scan: {e}")

@app.post("/api/files/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload audio files for processing"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    results = []
    for file in files:
        try:
            # Validate file type
            if not file.filename.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "message": "Unsupported file type"
                })
                continue

            # For now, just acknowledge the upload
            results.append({
                "filename": file.filename,
                "status": "success",
                "message": "File upload simulation - processing not yet implemented"
            })

        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "message": str(e)
            })

    return {"results": results}

@app.get("/api/audio/formats")
async def get_supported_formats():
    """Get supported audio formats"""
    return {
        "input_formats": [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"],
        "output_formats": [".wav", ".flac", ".mp3"],
        "sample_rates": [44100, 48000, 88200, 96000, 192000],
        "bit_depths": [16, 24, 32]
    }

# Enhanced Audio Player API Endpoints

@app.get("/api/player/status")
async def get_player_status():
    """Get current player status"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        status = {
            "state": audio_player.state.value if hasattr(audio_player.state, 'value') else str(audio_player.state),
            "volume": getattr(audio_player, 'volume', 1.0),
            "position": audio_player.get_position() if hasattr(audio_player, 'get_position') else 0,
            "duration": audio_player.get_duration() if hasattr(audio_player, 'get_duration') else 0,
            "current_track": audio_player.get_current_track() if hasattr(audio_player, 'get_current_track') else None,
            "queue_size": len(audio_player.queue_manager.queue) if hasattr(audio_player, 'queue_manager') else 0,
            "shuffle_enabled": getattr(audio_player, 'shuffle_enabled', False),
            "repeat_mode": getattr(audio_player, 'repeat_mode', 'none'),
        }

        # Get real-time analysis if available
        if hasattr(audio_player, 'get_real_time_analysis'):
            try:
                analysis = audio_player.get_real_time_analysis()
                status["analysis"] = analysis
            except:
                status["analysis"] = None

        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get player status: {e}")

@app.post("/api/player/load")
async def load_track(track_path: str):
    """Load a track into the player"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        # Add to queue and load
        audio_player.add_to_queue(track_path)
        success = audio_player.load_current_track() if hasattr(audio_player, 'load_current_track') else True

        if success:
            # Broadcast to all connected clients
            await manager.broadcast({
                "type": "track_loaded",
                "data": {"track_path": track_path}
            })
            return {"message": "Track loaded successfully", "track_path": track_path}
        else:
            raise HTTPException(status_code=400, detail="Failed to load track")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load track: {e}")

@app.post("/api/player/play")
async def play_audio():
    """Start playback"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        audio_player.play()

        # Broadcast to all connected clients
        await manager.broadcast({
            "type": "playback_started",
            "data": {"state": "playing"}
        })

        return {"message": "Playback started", "state": "playing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start playback: {e}")

@app.post("/api/player/pause")
async def pause_audio():
    """Pause playback"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        audio_player.pause()

        # Broadcast to all connected clients
        await manager.broadcast({
            "type": "playback_paused",
            "data": {"state": "paused"}
        })

        return {"message": "Playback paused", "state": "paused"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause playback: {e}")

@app.post("/api/player/stop")
async def stop_audio():
    """Stop playback"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        audio_player.stop()

        # Broadcast to all connected clients
        await manager.broadcast({
            "type": "playback_stopped",
            "data": {"state": "stopped"}
        })

        return {"message": "Playback stopped", "state": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop playback: {e}")

@app.post("/api/player/seek")
async def seek_position(position: float):
    """Seek to position in seconds"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'seek_to_position'):
            audio_player.seek_to_position(position)

        # Broadcast to all connected clients
        await manager.broadcast({
            "type": "position_changed",
            "data": {"position": position}
        })

        return {"message": "Position updated", "position": position}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to seek: {e}")

@app.post("/api/player/volume")
async def set_volume(volume: float):
    """Set playback volume (0.0 to 1.0)"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        # Clamp volume to valid range
        volume = max(0.0, min(1.0, volume))

        if hasattr(audio_player, 'set_volume'):
            audio_player.set_volume(volume)

        # Broadcast to all connected clients
        await manager.broadcast({
            "type": "volume_changed",
            "data": {"volume": volume}
        })

        return {"message": "Volume updated", "volume": volume}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set volume: {e}")

@app.get("/api/player/queue")
async def get_queue():
    """Get current playback queue"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'queue_manager'):
            queue_info = audio_player.queue_manager.get_queue_info() if hasattr(audio_player.queue_manager, 'get_queue_info') else {
                "tracks": list(audio_player.queue_manager.queue),
                "current_index": audio_player.queue_manager.current_index,
                "total_tracks": len(audio_player.queue_manager.queue)
            }
            return queue_info
        else:
            return {"tracks": [], "current_index": 0, "total_tracks": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get queue: {e}")

@app.post("/api/player/queue/add")
async def add_to_queue(track_path: str):
    """Add track to playback queue"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        audio_player.add_to_queue(track_path)

        # Broadcast queue update
        await manager.broadcast({
            "type": "queue_updated",
            "data": {"action": "added", "track_path": track_path}
        })

        return {"message": "Track added to queue", "track_path": track_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add to queue: {e}")

@app.post("/api/player/next")
async def next_track():
    """Skip to next track"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'next_track'):
            success = audio_player.next_track()
            if success:
                await manager.broadcast({
                    "type": "track_changed",
                    "data": {"action": "next"}
                })
                return {"message": "Skipped to next track"}
            else:
                return {"message": "No next track available"}
        else:
            return {"message": "Next track function not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to skip track: {e}")

@app.post("/api/player/previous")
async def previous_track():
    """Skip to previous track"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'previous_track'):
            success = audio_player.previous_track()
            if success:
                await manager.broadcast({
                    "type": "track_changed",
                    "data": {"action": "previous"}
                })
                return {"message": "Skipped to previous track"}
            else:
                return {"message": "No previous track available"}
        else:
            return {"message": "Previous track function not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to skip track: {e}")

# Audio Processing Control Endpoints

@app.post("/api/processing/enable_matching")
async def enable_level_matching(enabled: bool):
    """Enable/disable real-time level matching"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'config'):
            audio_player.config.enable_level_matching = enabled

        await manager.broadcast({
            "type": "processing_changed",
            "data": {"level_matching": enabled}
        })

        return {"message": f"Level matching {'enabled' if enabled else 'disabled'}", "enabled": enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle level matching: {e}")

@app.post("/api/processing/load_reference")
async def load_reference_track(reference_path: str):
    """Load reference track for level matching"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        if hasattr(audio_player, 'load_reference'):
            success = audio_player.load_reference(reference_path)
            if success:
                await manager.broadcast({
                    "type": "reference_loaded",
                    "data": {"reference_path": reference_path}
                })
                return {"message": "Reference track loaded", "reference_path": reference_path}
            else:
                raise HTTPException(status_code=400, detail="Failed to load reference track")
        else:
            return {"message": "Reference loading not supported"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load reference: {e}")

@app.post("/api/processing/apply_preset")
async def apply_processing_preset(preset_name: str, settings: dict):
    """Apply a processing preset"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        logger.info(f"Applying preset '{preset_name}' with settings: {settings}")

        # Store the preset settings (in a real implementation, this would apply to the audio processing)
        # For now, we'll just broadcast the settings
        await manager.broadcast({
            "type": "preset_applied",
            "data": {
                "preset_name": preset_name,
                "settings": settings
            }
        })

        return {"message": f"Preset '{preset_name}' applied successfully", "settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply preset: {e}")

@app.get("/api/processing/analysis")
async def get_audio_analysis():
    """Get real-time audio analysis data"""
    if not audio_player:
        raise HTTPException(status_code=503, detail="Audio player not available")

    try:
        # Mock analysis data for now
        analysis = {
            "peak_level": 0.7 + (0.3 * __import__('random').random()),
            "rms_level": 0.4 + (0.2 * __import__('random').random()),
            "frequency_spectrum": [
                0.1 + (0.6 * __import__('random').random()) for _ in range(64)
            ],
            "dynamic_range": 12.5,
            "lufs": -16.2
        }

        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analysis: {e}")

@app.post("/api/comparison/load_tracks")
async def load_comparison_tracks(track_a: str, track_b: str):
    """Load tracks for A/B comparison"""
    try:
        # This would load both tracks into separate players
        # For now, we'll simulate the loading
        await manager.broadcast({
            "type": "comparison_tracks_loaded",
            "data": {
                "track_a": track_a,
                "track_b": track_b,
                "ready": True
            }
        })

        return {
            "message": "A/B comparison tracks loaded",
            "track_a": track_a,
            "track_b": track_b
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load comparison tracks: {e}")

# Serve React frontend (when built)
# Check if running from PyInstaller bundle
if hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle - frontend is bundled in _MEIPASS/frontend
    frontend_path = Path(sys._MEIPASS) / "frontend"
    logger.info(f"PyInstaller mode: _MEIPASS={sys._MEIPASS}")
else:
    # Development mode - look in regular location
    frontend_path = Path(__file__).parent.parent / "frontend" / "build"

logger.info(f"Looking for frontend at: {frontend_path}")
if frontend_path.exists():
    logger.info(f"✅ Serving frontend from: {frontend_path}")
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
else:
    logger.warning(f"⚠️  Frontend not found at {frontend_path}")
    @app.get("/")
    async def root():
        return HTMLResponse(f"""
        <html>
            <head><title>Auralis Web</title></head>
            <body>
                <h1>🎵 Auralis Web Backend</h1>
                <p>FastAPI backend is running!</p>
                <p>Frontend not found at: {frontend_path}</p>
                <p><a href="/api/docs">View API Documentation</a></p>
            </body>
        </html>
        """)

if __name__ == "__main__":
    print("🚀 Starting Auralis Web Backend...")
    print("Backend ready", flush=True)  # Signal to Electron that backend is ready

    # Detect if running in PyInstaller bundle (production mode)
    import sys
    is_bundled = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8765,
        reload=False if is_bundled else True,  # Disable reload in production
        log_level="info"
    )