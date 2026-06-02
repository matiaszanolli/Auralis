"""
API Routers for Auralis Web Backend

Modular router organization for maintainability.
Each router handles a specific domain of the API.
"""

from .artwork import create_artwork_router
from .enhancement import create_enhancement_router
from .files import create_files_router
from .library import create_library_router
from .tracks import create_tracks_router
from .library_scan import create_library_scan_router
from .fingerprint_status import create_fingerprint_status_router
from .player import create_player_router
from .playlists import create_playlists_router

# Completed routers
from .system import create_system_router

from .health import create_health_router

__all__ = [
    'create_health_router',
    'create_system_router',
    'create_files_router',
    'create_enhancement_router',
    'create_artwork_router',
    'create_playlists_router',
    'create_library_router',
    'create_tracks_router',
    'create_library_scan_router',
    'create_fingerprint_status_router',
    'create_player_router',
]
