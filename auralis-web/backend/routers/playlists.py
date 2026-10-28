"""
Playlists Router
~~~~~~~~~~~~~~~~

Playlist CRUD and track management; every route is registered at the bottom of this module.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends

from .playlists_models import (
    AddTracksResponse,
    CreatePlaylistResponse,
    PlaylistDetailResponse,
    PlaylistListResponse,
    PlaylistMessageResponse,
)
from .playlists_deps import _PlaylistsDeps, _deps, _repo_deps
from .playlists_tracks import (
    add_track_to_playlist,
    add_tracks_to_playlist,
    clear_playlist,
    remove_track_from_playlist,
    reorder_playlist_track,
)
from .playlists_crud import (
    create_playlist,
    delete_playlist,
    get_playlist,
    get_playlists,
    update_playlist,
)


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_playlists_router() used to be a ~400-line closure: every handler
# below was nested inside it purely to reach get_repository_factory and
# connection_manager via closure capture, which made a handler impossible to
# import or call without first building the whole router. Handlers are now
# module level; they reach the same callables through FastAPI Depends()
# instead.
#
# Factory calls can coexist in one process (the live app plus throwaway test
# apps), so each router publishes its own deps through a request ContextVar.
# The module-level holder is only the fallback for direct handler calls where
# no router-level dependency ran (#5262).
#
# A handler's Depends() default is only consulted when FastAPI itself
# invokes it for a real request; a direct unit-test call passes the
# repos/connection_manager explicitly as a keyword argument and never
# touches _PlaylistsDeps at all -- that's the seam #4670 asked for.
# ============================================================================


def create_playlists_router(
    get_repository_factory: Callable[[], Any],
    connection_manager: Any
) -> APIRouter:
    """
    Factory function to create playlists router with dependencies.

    Args:
        get_repository_factory: Callable that returns RepositoryFactory instance
        connection_manager: WebSocket connection manager for broadcasts

    Returns:
        APIRouter: Configured router instance

    Note:
    """
    deps = _PlaylistsDeps(connection_manager)

    router = APIRouter(
        tags=["playlists"],
        dependencies=[
            Depends(_repo_deps.bind(get_repository_factory)),
            Depends(_deps.bind(deps)),
        ],
    )

    router.add_api_route("/api/playlists", get_playlists, methods=["GET"], response_model=PlaylistListResponse)
    router.add_api_route("/api/playlists/{playlist_id}", get_playlist, methods=["GET"], response_model=PlaylistDetailResponse)
    router.add_api_route("/api/playlists", create_playlist, methods=["POST"], response_model=CreatePlaylistResponse)
    router.add_api_route("/api/playlists/{playlist_id}", update_playlist, methods=["PUT"], response_model=PlaylistMessageResponse)
    router.add_api_route("/api/playlists/{playlist_id}", delete_playlist, methods=["DELETE"], response_model=PlaylistMessageResponse)

    # Track routes. The literal `/tracks/add` and `/tracks/reorder` paths are
    # registered before `/tracks/{track_id}`, matching the original decorator
    # order — that ordering is load-bearing for path matching (#4658).
    router.add_api_route("/api/playlists/{playlist_id}/tracks", add_tracks_to_playlist, methods=["POST"], response_model=AddTracksResponse)
    router.add_api_route("/api/playlists/{playlist_id}/tracks/add", add_track_to_playlist, methods=["POST"], response_model=PlaylistMessageResponse)
    router.add_api_route("/api/playlists/{playlist_id}/tracks/reorder", reorder_playlist_track, methods=["PUT"], response_model=PlaylistMessageResponse)
    router.add_api_route("/api/playlists/{playlist_id}/tracks/{track_id}", remove_track_from_playlist, methods=["DELETE"], response_model=PlaylistMessageResponse)
    router.add_api_route("/api/playlists/{playlist_id}/tracks", clear_playlist, methods=["DELETE"], response_model=PlaylistMessageResponse)

    return router
