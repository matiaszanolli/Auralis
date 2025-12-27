"""
API Routers for Auralis Web Backend

Modular router organization for maintainability.
Each router handles a specific domain of the API.
"""

from .artwork import create_artwork_router
from .enhancement import create_enhancement_router
from .files import create_files_router
from .library import create_library_router
from .player import create_player_router
from .playlists import create_playlists_router

# Completed routers
from .system import create_system_router

__all__ = [
    'create_system_router',
    'create_files_router',
    'create_enhancement_router',
    'create_artwork_router',
    'create_playlists_router',
    'create_library_router',
    'create_player_router',
]
