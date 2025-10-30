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

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn
import asyncio
import json
import sys
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

# Import state management
from player_state import PlayerState, TrackInfo, create_track_info
from state_manager import PlayerStateManager
from proactive_buffer import buffer_presets_for_track

# Add parent directory to path for Auralis imports
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from auralis.library import LibraryManager
    from auralis.library.scanner import LibraryScanner
    from auralis.library.repositories.settings_repository import SettingsRepository
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
    from chunked_processor import ChunkedAudioProcessor
    HAS_PROCESSING = True
except ImportError as e:
    print(f"⚠️  Processing components not available: {e}")
    HAS_PROCESSING = False
    ChunkedAudioProcessor = None

# Import multi-tier buffer system
try:
    from multi_tier_buffer import MultiTierBufferManager
    from multi_tier_worker import MultiTierBufferWorker
    from routers.cache import create_cache_router
    HAS_MULTI_TIER = True
except ImportError as e:
    print(f"⚠️  Multi-tier buffer not available: {e}")
    HAS_MULTI_TIER = False

# Import routers
from routers.system import create_system_router
from routers.files import create_files_router
from routers.enhancement import create_enhancement_router
from routers.artwork import create_artwork_router
from routers.playlists import create_playlists_router
from routers.library import create_library_router
from routers.albums import create_albums_router
from routers.artists import create_artists_router
from routers.player import create_player_router
from routers.metadata import create_metadata_router
from routers.mse_streaming import create_mse_streaming_router
from routers.unified_streaming import create_unified_streaming_router
from routers.similarity import create_similarity_router

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
    allow_origins=[
        "http://localhost:3000",      # React dev server
        "http://127.0.0.1:3000",
        "http://localhost:8765",      # Production (same-origin but explicit)
        "http://127.0.0.1:8765",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include processing API routes
if HAS_PROCESSING:
    app.include_router(processing_router)

# Global state
library_manager: Optional[LibraryManager] = None
settings_repository: Optional[SettingsRepository] = None
audio_player: Optional[EnhancedAudioPlayer] = None
processing_cache: dict = {}  # Cache for processed audio files
player_state_manager: Optional[PlayerStateManager] = None
if HAS_PROCESSING:
    processing_engine: Optional[ProcessingEngine] = None
else:
    processing_engine = None
connected_websockets: List[WebSocket] = []

# Multi-tier buffer system
multi_tier_manager: Optional[MultiTierBufferManager] = None
multi_tier_worker: Optional[MultiTierBufferWorker] = None

# Similarity system (fingerprint-based music similarity)
try:
    from auralis.analysis.fingerprint import FingerprintSimilarity, KNNGraphBuilder
    similarity_system: Optional[FingerprintSimilarity] = None
    graph_builder: Optional[KNNGraphBuilder] = None
    HAS_SIMILARITY = True
except ImportError as e:
    logger.warning(f"⚠️  Similarity system not available: {e}")
    similarity_system = None
    graph_builder = None
    HAS_SIMILARITY = False

# Initialize Auralis components
@app.on_event("startup")
async def startup_event():
    """Initialize Auralis components on startup"""
    global library_manager, settings_repository, audio_player, processing_engine, processing_cache
    global similarity_system, graph_builder

    # Clear processing cache on startup to avoid serving stale processed audio
    processing_cache.clear()
    logger.info("🧹 Processing cache cleared on startup")

    # Clear chunk files from disk to avoid serving stale chunks with old presets
    import tempfile
    import shutil
    chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"
    if chunk_dir.exists():
        try:
            shutil.rmtree(chunk_dir)
            chunk_dir.mkdir(exist_ok=True)
            logger.info(f"🧹 Cleared chunk directory: {chunk_dir}")
        except Exception as e:
            logger.warning(f"Failed to clear chunk directory: {e}")

    if HAS_AURALIS:
        try:
            library_manager = LibraryManager()
            logger.info("✅ Auralis LibraryManager initialized")

            # Initialize settings repository
            settings_repository = SettingsRepository(library_manager.SessionLocal)
            logger.info("✅ Settings Repository initialized")

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

            # Initialize state manager (must be after manager is created)
            global player_state_manager
            player_state_manager = PlayerStateManager(manager)
            logger.info("✅ Player State Manager initialized")

            # Initialize similarity system
            if HAS_SIMILARITY:
                try:
                    similarity_system = FingerprintSimilarity(library_manager.fingerprints)
                    logger.info("✅ Fingerprint Similarity System initialized")

                    # Only create graph_builder if system is already fitted
                    # (will be created on-demand via /api/similarity/fit endpoint)
                    if similarity_system.is_fitted():
                        graph_builder = KNNGraphBuilder(
                            similarity_system=similarity_system,
                            session_factory=library_manager.SessionLocal
                        )
                        logger.info("✅ K-NN Graph Builder initialized (system is fitted)")
                    else:
                        graph_builder = None
                        logger.info("ℹ️  K-NN Graph Builder not initialized (system not fitted yet)")
                except Exception as sim_e:
                    logger.warning(f"⚠️  Failed to initialize Similarity System: {sim_e}")
                    similarity_system = None
                    graph_builder = None

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

    # Initialize multi-tier buffer system
    if HAS_MULTI_TIER and library_manager:
        try:
            global multi_tier_manager, multi_tier_worker

            multi_tier_manager = MultiTierBufferManager()
            logger.info("✅ Multi-Tier Buffer Manager initialized")

            multi_tier_worker = MultiTierBufferWorker(
                buffer_manager=multi_tier_manager,
                library_manager=library_manager
            )

            # Start the worker
            await multi_tier_worker.start()
            logger.info("✅ Multi-Tier Buffer Worker started")

        except Exception as e:
            logger.error(f"❌ Failed to initialize multi-tier buffer: {e}")
    else:
        if not HAS_MULTI_TIER:
            logger.warning("⚠️  Multi-tier buffer not available")
        elif not library_manager:
            logger.warning("⚠️  Library manager not available - multi-tier buffer disabled")

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

# Create and include system router (health, version, WebSocket)
system_router = create_system_router(
    manager=manager,
    get_library_manager=lambda: library_manager,
    get_processing_engine=lambda: processing_engine,
    HAS_AURALIS=HAS_AURALIS
)
app.include_router(system_router)

# Create and include files router (scan, upload, formats)
files_router = create_files_router(
    get_library_manager=lambda: library_manager,
    connection_manager=manager
)
app.include_router(files_router)

# Create and include enhancement router (toggle, preset, intensity, status, cache clear)
enhancement_router = create_enhancement_router(
    get_enhancement_settings=lambda: enhancement_settings,
    connection_manager=manager,
    get_processing_cache=lambda: processing_cache
)
app.include_router(enhancement_router)

# Create and include artwork router (get, extract, delete)
artwork_router = create_artwork_router(
    get_library_manager=lambda: library_manager,
    connection_manager=manager
)
app.include_router(artwork_router)

# Create and include playlists router (CRUD + track management)
playlists_router = create_playlists_router(
    get_library_manager=lambda: library_manager,
    connection_manager=manager
)
app.include_router(playlists_router)

# Create and include library router (stats, tracks, albums, artists)
library_router = create_library_router(
    get_library_manager=lambda: library_manager
)
app.include_router(library_router)

# Create and include metadata router (track metadata editing)
metadata_router = create_metadata_router(
    get_library_manager=lambda: library_manager,
    broadcast_manager=manager
)
app.include_router(metadata_router)

# Create and include albums router (album browsing and management)
albums_router = create_albums_router(
    get_library_manager=lambda: library_manager
)
app.include_router(albums_router)

# Create and include artists router (artist browsing and management)
artists_router = create_artists_router(
    get_library_manager=lambda: library_manager
)
app.include_router(artists_router)

# Create and include player router (playback control, streaming, queue management)
player_router = create_player_router(
    get_library_manager=lambda: library_manager,
    get_audio_player=lambda: audio_player,
    get_player_state_manager=lambda: player_state_manager,
    get_processing_cache=lambda: processing_cache,
    connection_manager=manager,
    chunked_audio_processor_class=ChunkedAudioProcessor,
    create_track_info_fn=create_track_info,
    buffer_presets_fn=buffer_presets_for_track
)
app.include_router(player_router)

# Include cache management router
if HAS_MULTI_TIER and multi_tier_manager:
    cache_router = create_cache_router(
        buffer_manager=multi_tier_manager,
        broadcast_manager=manager
    )
    app.include_router(cache_router, prefix="/api")
    logger.info("✅ Cache management router included")

# Include MSE streaming router
mse_router = create_mse_streaming_router(
    get_library_manager=lambda: library_manager,
    get_multi_tier_buffer=lambda: multi_tier_manager if HAS_MULTI_TIER else None,
    chunked_audio_processor_class=ChunkedAudioProcessor,
    chunk_duration=30
)
app.include_router(mse_router)
logger.info("✅ MSE streaming router included")

# Include Unified streaming router (MSE + Multi-Tier Buffer integration)
unified_router = create_unified_streaming_router(
    get_library_manager=lambda: library_manager,
    get_multi_tier_buffer=lambda: multi_tier_manager if HAS_MULTI_TIER else None,
    chunked_processor_class=ChunkedAudioProcessor,
    chunk_duration=30.0
)
app.include_router(unified_router)
logger.info("✅ Unified streaming router included (MSE + MTB integration)")

# Create and include similarity router (fingerprint-based music similarity)
if HAS_SIMILARITY:
    similarity_router = create_similarity_router(
        get_library_manager=lambda: library_manager,
        get_similarity_system=lambda: similarity_system,
        get_graph_builder=lambda: graph_builder
    )
    app.include_router(similarity_router)
    logger.info("✅ Similarity router included (25D fingerprint similarity)")
else:
    logger.warning("⚠️  Similarity router not available (missing dependencies)")

# OLD WebSocket endpoint - KEEPING FOR NOW, WILL REMOVE AFTER TESTING
# TODO: Remove these old endpoints after verifying router works
# ============================================================================

class CreatePlaylistRequest(BaseModel):
    name: str
    description: str = ""
    track_ids: List[int] = []

class UpdatePlaylistRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class AddTracksRequest(BaseModel):
    track_ids: List[int]

# ============================================================================
# END PLAYLIST ENDPOINTS

# ============================================================================
# ALBUM ARTWORK ENDPOINTS

# ============================================================================
# END ARTWORK ENDPOINTS
# ============================================================================

class ScanRequest(BaseModel):
    directory: str

# ============================================================================

# Global enhancement state
enhancement_settings = {
    "enabled": False,
    "preset": "adaptive",
    "intensity": 1.0
}

# ============================================================================

class SetQueueRequest(BaseModel):
    tracks: List[int]  # Track IDs
    start_index: int = 0

class ReorderQueueRequest(BaseModel):
    new_order: List[int]  # New order of track indices

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


# ========================================
# SETTINGS API ENDPOINTS
# ========================================

@app.get("/api/settings")
async def get_settings():
    """Get current user settings"""
    if not settings_repository:
        raise HTTPException(status_code=503, detail="Settings not available")

    try:
        settings = settings_repository.get_settings()
        return settings.to_dict()
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {e}")


class SettingsUpdate(BaseModel):
    """Pydantic model for settings updates"""
    # Library
    scan_folders: Optional[List[str]] = None
    file_types: Optional[List[str]] = None
    auto_scan: Optional[bool] = None
    scan_interval: Optional[int] = None

    # Playback
    crossfade_enabled: Optional[bool] = None
    crossfade_duration: Optional[float] = None
    gapless_enabled: Optional[bool] = None
    replay_gain_enabled: Optional[bool] = None
    volume: Optional[float] = None

    # Audio
    output_device: Optional[str] = None
    bit_depth: Optional[int] = None
    sample_rate: Optional[int] = None

    # Interface
    theme: Optional[str] = None
    language: Optional[str] = None
    show_visualizations: Optional[bool] = None
    mini_player_on_close: Optional[bool] = None

    # Enhancement
    default_preset: Optional[str] = None
    auto_enhance: Optional[bool] = None
    enhancement_intensity: Optional[float] = None

    # Advanced
    cache_size: Optional[int] = None
    max_concurrent_scans: Optional[int] = None
    enable_analytics: Optional[bool] = None
    debug_mode: Optional[bool] = None


@app.put("/api/settings")
async def update_settings(updates: SettingsUpdate):
    """Update user settings"""
    if not settings_repository:
        raise HTTPException(status_code=503, detail="Settings not available")

    try:
        # Convert to dictionary and remove None values
        updates_dict = {k: v for k, v in updates.dict().items() if v is not None}

        # Update settings
        settings = settings_repository.update_settings(updates_dict)

        # Broadcast settings changed event
        await manager.broadcast({
            "type": "settings_changed",
            "data": settings.to_dict()
        })

        return {
            "message": "Settings updated successfully",
            "settings": settings.to_dict()
        }
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {e}")


@app.post("/api/settings/reset")
async def reset_settings():
    """Reset all settings to defaults"""
    if not settings_repository:
        raise HTTPException(status_code=503, detail="Settings not available")

    try:
        settings = settings_repository.reset_to_defaults()

        # Broadcast settings reset event
        await manager.broadcast({
            "type": "settings_reset",
            "data": settings.to_dict()
        })

        return {
            "message": "Settings reset to defaults",
            "settings": settings.to_dict()
        }
    except Exception as e:
        logger.error(f"Failed to reset settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {e}")


class ScanFolderRequest(BaseModel):
    """Request to add a scan folder"""
    folder: str


@app.post("/api/settings/scan-folders")
async def add_scan_folder(request: ScanFolderRequest):
    """Add a new folder to scan list"""
    if not settings_repository:
        raise HTTPException(status_code=503, detail="Settings not available")

    try:
        settings = settings_repository.add_scan_folder(request.folder)

        await manager.broadcast({
            "type": "scan_folder_added",
            "data": {"folder": request.folder}
        })

        return {
            "message": f"Added scan folder: {request.folder}",
            "settings": settings.to_dict()
        }
    except Exception as e:
        logger.error(f"Failed to add scan folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add scan folder: {e}")


@app.delete("/api/settings/scan-folders")
async def remove_scan_folder(request: ScanFolderRequest):
    """Remove a folder from scan list"""
    if not settings_repository:
        raise HTTPException(status_code=503, detail="Settings not available")

    try:
        settings = settings_repository.remove_scan_folder(request.folder)

        await manager.broadcast({
            "type": "scan_folder_removed",
            "data": {"folder": request.folder}
        })

        return {
            "message": f"Removed scan folder: {request.folder}",
            "settings": settings.to_dict()
        }
    except Exception as e:
        logger.error(f"Failed to remove scan folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove scan folder: {e}")


# Serve React frontend (when built)
# Check if running in Electron (packaged app)
if os.environ.get('ELECTRON_MODE'):
    # Running in Electron - frontend is in Resources/frontend
    # Backend is in Resources/backend/auralis-backend
    # Get Resources directory by going up from executable location
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller bundled - go up from _MEIPASS to Resources
        resources_path = Path(sys._MEIPASS).parent.parent
        frontend_path = resources_path / "frontend"
        logger.info(f"Electron + PyInstaller mode: Resources={resources_path}")
    else:
        # Not bundled (shouldn't happen in Electron, but handle it)
        frontend_path = Path(__file__).parent.parent / "frontend" / "build"
elif hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle but not Electron - frontend might be bundled
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
        app,  # Pass app directly instead of "main:app" to avoid module duplication
        host="127.0.0.1",
        port=8765,
        log_level="info"
    )