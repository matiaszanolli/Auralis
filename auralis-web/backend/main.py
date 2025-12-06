#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auralis Web Backend

Modern FastAPI backend for Auralis audio processing and library management.
Replaces the Tkinter GUI with a professional web interface.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import uvicorn
import logging
import sys
import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path for Auralis imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import configuration modules
from config.app import create_app
from config.middleware import setup_middleware
from config.startup import setup_startup_handlers
from config.routes import setup_routers
from config.globals import ConnectionManager

# Import state management
from player_state import create_track_info
from proactive_buffer import buffer_presets_for_track

# Check feature availability
HAS_AURALIS = True
HAS_PROCESSING = True
HAS_STREAMLINED_CACHE = True
HAS_SIMILARITY = True

# Import core components for router setup
try:
    from processing_engine import ProcessingEngine
    from chunked_processor import ChunkedAudioProcessor
except ImportError:
    HAS_PROCESSING = False
    ProcessingEngine = None
    ChunkedAudioProcessor = None
    logger.warning("⚠️  Processing components not available")

try:
    from cache import StreamlinedCacheManager
    from streamlined_worker import StreamlinedCacheWorker
except ImportError:
    HAS_STREAMLINED_CACHE = False
    logger.warning("⚠️  Streamlined cache not available")

try:
    from auralis.analysis.fingerprint import FingerprintSimilarity, KNNGraphBuilder
except ImportError:
    HAS_SIMILARITY = False
    logger.warning("⚠️  Similarity system not available")

# Create FastAPI application
app = create_app()

# Setup middleware
setup_middleware(app)

# Create global state dictionary with all dependencies
manager = ConnectionManager()
globals_dict = {
    # Components (initialized during startup)
    'library_manager': None,
    'settings_repository': None,
    'audio_player': None,
    'player_state_manager': None,
    'processing_cache': {},
    'processing_engine': None,
    'streamlined_cache': None,
    'streamlined_worker': None,
    'similarity_system': None,
    'graph_builder': None,
    # Configuration
    'enhancement_settings': {
        "enabled": True,
        "preset": "adaptive",
        "intensity": 1.0
    },
}

# Prepare dependencies dictionary for startup and routers
deps = {
    'HAS_AURALIS': HAS_AURALIS,
    'HAS_PROCESSING': HAS_PROCESSING,
    'HAS_STREAMLINED_CACHE': HAS_STREAMLINED_CACHE,
    'HAS_SIMILARITY': HAS_SIMILARITY,
    'manager': manager,
    'globals': globals_dict,
    'enhancement_settings': globals_dict['enhancement_settings'],
    'processing_cache': globals_dict['processing_cache'],
    'chunked_audio_processor_class': ChunkedAudioProcessor,
    'create_track_info_fn': create_track_info,
    'buffer_presets_fn': buffer_presets_for_track,
}

# Setup startup/shutdown handlers (populates globals_dict during startup)
setup_startup_handlers(app, deps)

# Setup routers (registers all routes with app)
setup_routers(app, deps)

# Frontend static file serving
if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle (production or Electron)
    frontend_path = Path(sys._MEIPASS) / "frontend"
    logger.info(f"PyInstaller mode: _MEIPASS={sys._MEIPASS}")
elif hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle but not Electron - frontend might be bundled
    frontend_path = Path(sys._MEIPASS) / "frontend"
    logger.info(f"PyInstaller mode: _MEIPASS={sys._MEIPASS}")
else:
    # Development mode - look in regular location
    frontend_path = Path(__file__).parent.parent / "frontend" / "build"

logger.info(f"Looking for frontend at: {frontend_path}")

# Only mount static files in production (when not running --dev)
# In development, Vite serves the frontend and proxies API requests
# StaticFiles mount at "/" interferes with WebSocket routes, so we must avoid it in dev mode
is_dev_mode = "--dev" in sys.argv or os.environ.get("DEV_MODE")

if not is_dev_mode and frontend_path.exists():
    logger.info(f"✅ Serving frontend from: {frontend_path} (production mode)")
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
elif is_dev_mode:
    logger.info("ℹ️  Development mode: Vite serves frontend, StaticFiles NOT mounted (preserves WebSocket routes)")

    @app.get("/")
    async def root():
        return HTMLResponse("""
        <html>
            <head><title>Auralis Web</title></head>
            <body>
                <h1>🎵 Auralis Web Backend</h1>
                <p>Backend API is running!</p>
                <p>Frontend served by Vite on http://localhost:3000+</p>
                <p><a href="/api/docs">View API Documentation</a></p>
            </body>
        </html>
        """)
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

    uvicorn.run(
        app,  # Pass app directly instead of "main:app" to avoid module duplication
        host="127.0.0.1",
        port=8765,
        log_level="info"
    )
