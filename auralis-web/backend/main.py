#!/usr/bin/env python3

"""
Auralis Web Backend

Modern FastAPI backend for Auralis audio processing and library management.
Replaces the Tkinter GUI with a professional web interface.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import html as html_module
import logging
import os
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path for Auralis imports
# Detect execution context and set appropriate path
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # Running as PyInstaller bundle (Electron AppImage)
    # Use working directory to find resources (cwd is set to resources/backend by Electron)
    auralis_parent = Path(os.getcwd()).parent
    logger.info(f"Running as PyInstaller bundle, adding to sys.path: {auralis_parent}")
    # Append (not insert) so that _MEIPASS — which PyInstaller puts at the front — takes
    # priority over the external resources/auralis/ copy, preventing a stale copy from
    # shadowing the auralis version that was bundled into this executable.
    sys.path.append(str(auralis_parent))
elif os.environ.get('ELECTRON_MODE') == '1':
    # Running in Electron but not frozen (shouldn't happen in production)
    auralis_parent = Path(__file__).parent.parent
    logger.info(f"Running in Electron mode (unfrozen), adding to sys.path: {auralis_parent}")
    sys.path.insert(0, str(auralis_parent))
else:
    # Running in development - auralis package is in ../../..
    auralis_parent = Path(__file__).parent.parent.parent
    logger.info(f"Running in development mode, adding to sys.path: {auralis_parent}")
    sys.path.insert(0, str(auralis_parent))

# Import configuration modules
from config.app import create_app
from config.globals import ConnectionManager
from config.middleware import setup_middleware
from config.routes import setup_routers
from config.startup import create_lifespan

# Import state management
from player_state import create_track_info
from core.proactive_buffer import buffer_presets_for_track

# Check feature availability
HAS_AURALIS = True
HAS_PROCESSING = True
HAS_STREAMLINED_CACHE = True
HAS_SIMILARITY = True

# Import core components for router setup
ProcessingEngine: Any = None
ChunkedAudioProcessor: Any = None
try:
    from core.chunked_processor import ChunkedAudioProcessor
except ImportError:
    HAS_PROCESSING = False
    logger.warning("⚠️  Processing components not available")

try:
    pass
except ImportError:
    HAS_STREAMLINED_CACHE = False
    logger.warning("⚠️  Streamlined cache not available")

try:
    pass
except ImportError:
    HAS_SIMILARITY = False
    logger.warning("⚠️  Similarity system not available")

# Create global state dictionary with all dependencies
manager = ConnectionManager()
globals_dict = {
    # Components (initialized during startup)
    'library_manager': None,
    'repository_factory': None,  # Phase 2: RepositoryFactory for DI
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

# Create lifespan context manager for startup/shutdown (populates globals_dict)
lifespan = create_lifespan(deps)

# Create FastAPI application with lifespan
app = create_app(lifespan=lifespan)

# Setup middleware
setup_middleware(app)

# Setup routers (registers all routes with app)
setup_routers(app, deps)

# Frontend static file serving
if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS') and os.environ.get('ELECTRON_MODE') == '1':
    # PyInstaller bundle running in Electron AppImage
    # Frontend is in resources/frontend, not in the PyInstaller bundle
    # Use working directory to find resources (cwd is resources/backend)
    frontend_path = Path(os.getcwd()).parent / "frontend"
    logger.info(f"Electron mode: looking for frontend at {frontend_path}")
elif hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle but not Electron - frontend might be bundled
    meipass = getattr(sys, '_MEIPASS')
    frontend_path = Path(meipass) / "frontend"
    logger.info(f"PyInstaller mode: _MEIPASS={meipass}")
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
    async def root() -> HTMLResponse:
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
    async def root() -> HTMLResponse:
        return HTMLResponse(f"""
        <html>
            <head><title>Auralis Web</title></head>
            <body>
                <h1>🎵 Auralis Web Backend</h1>
                <p>FastAPI backend is running!</p>
                <p>Frontend not found at: {html_module.escape(str(frontend_path))}</p>
                <p><a href="/api/docs">View API Documentation</a></p>
            </body>
        </html>
        """)


if __name__ == "__main__":
    print("🚀 Starting Auralis Web Backend...", flush=True)

    uvicorn.run(
        app,  # Pass app directly instead of "main:app" to avoid module duplication
        host="127.0.0.1",
        port=8765,
        log_level="info"
    )
