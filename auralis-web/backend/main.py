#!/usr/bin/env python3

"""
Auralis Web Backend

Modern FastAPI backend for Auralis audio processing and library management.
Replaces the Tkinter GUI with a professional web interface.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from pathlib import Path

import uvicorn

# Bootstrap FIRST (#5834): the root logger must exist before any module logs
# (#4774), and sys.path must reach `auralis` before anything below imports it
# (the PyInstaller-frozen case; see config/bootstrap.py). These two imports
# are the only ones allowed above the sys.path call.
from config.bootstrap import configure_logging, configure_sys_path, early_dev_mode

_BACKEND_DIR = Path(__file__).parent
_log_level = configure_logging(early_dev_mode())
logger = logging.getLogger(__name__)
configure_sys_path(_BACKEND_DIR)

# Import configuration modules
from config.app import create_app
from config.bootstrap import install_log_sanitizer
from config.fallback_routes import mount_frontend, register_fallback_routes
from config.globals import ConnectionManager, set_component_registry
from config.limits import WS_MAX_MESSAGE_SIZE
from config.middleware import setup_middleware
from config.origins import BACKEND_PORT
from config.routes import setup_routers
from config.startup import create_lifespan
from schemas import DEFAULT_PRESET

install_log_sanitizer()

# Import state management
from player_state import create_track_info

# The engine, processing, cache and similarity packages are imported unguarded
# by the modules loaded above (and by the routers registered below), so this
# process has no degraded mode to probe for. The flags remain in `deps` as the
# startup/router seam: tests start the lifespan and build routers with a
# component switched off.
HAS_AURALIS = True
HAS_PROCESSING = True
HAS_STREAMLINED_CACHE = True
HAS_SIMILARITY = True

# Create global state dictionary with all dependencies
manager = ConnectionManager()
globals_dict = {
    # Components (initialized during startup)
    'library_database': None,
    'repository_factory': None,  # Phase 2: RepositoryFactory for DI
    'settings_repository': None,
    'audio_player': None,
    'player_state_manager': None,
    'processing_engine': None,
    'streamlined_cache': None,
    'streamlined_worker': None,
    'similarity_system': None,
    'graph_builder': None,
    # Configuration
    'enhancement_settings': {
        "enabled": True,
        "preset": DEFAULT_PRESET,
        "intensity": 1.0
    },
}

# Register this dict as THE process-wide component registry (#4578). Modules
# that cannot be passed dependencies explicitly — notably
# ChunkedAudioProcessor's Tier-1 fingerprint accessor — resolve components
# through config.globals.get_component_registry(). Startup mutates this same
# object in place, so those readers observe components as they are populated.
set_component_registry(globals_dict)

# Prepare dependencies dictionary for startup and routers
deps = {
    'HAS_AURALIS': HAS_AURALIS,
    'HAS_PROCESSING': HAS_PROCESSING,
    'HAS_STREAMLINED_CACHE': HAS_STREAMLINED_CACHE,
    'HAS_SIMILARITY': HAS_SIMILARITY,
    'manager': manager,
    'globals': globals_dict,
    'enhancement_settings': globals_dict['enhancement_settings'],
    'create_track_info_fn': create_track_info,
}

# Create lifespan context manager for startup/shutdown (populates globals_dict)
lifespan = create_lifespan(deps)

# Create FastAPI application with lifespan
app = create_app(lifespan=lifespan)

# Setup middleware
setup_middleware(app)

# Setup routers (registers all routes with app)
setup_routers(app, deps)

# Catch-alls for unregistered WebSocket paths and unmatched /api paths: after
# the real routes above, before the StaticFiles mount below (config/fallback_routes.py).
register_fallback_routes(app)

# Frontend: StaticFiles in production, a stub page in dev or when it is missing.
mount_frontend(app, _BACKEND_DIR)


if __name__ == "__main__":
    # AURALIS_PORT (#4805): launch-auralis-web.py threads --port through this env var.
    _port = BACKEND_PORT
    print(f"🚀 Starting Auralis Web Backend on port {_port}...", flush=True)

    uvicorn.run(
        app,  # Pass app directly instead of "main:app" to avoid module duplication
        host="127.0.0.1",
        port=_port,
        ws_max_size=WS_MAX_MESSAGE_SIZE,  # bound frames at the transport, before buffering: #5915
        log_level=_log_level,  # the level the root logger was configured with at import: #5065
        log_config=None,  # uvicorn's stock handlers bypass the sanitizing root handler: #6184
        proxy_headers=False,  # no reverse proxy: X-Forwarded-For must not rewrite the client IP: #6168
    )
