"""
Metadata Router
~~~~~~~~~~~~~~~

Handles track metadata editing operations.

Endpoints:
- GET /api/metadata/tracks/{track_id}/fields - Get editable fields for a track
- GET /api/metadata/tracks/{track_id} - Get current metadata for a track
- PUT /api/metadata/tracks/{track_id} - Update metadata for a track
- POST /api/metadata/batch - Batch update metadata for multiple tracks

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends

from auralis.library.metadata_editor import MetadataEditor

from .metadata_models import (
    BatchMetadataResponse,
    EditableFieldsResponse,
    MetadataUpdateResponse,
    TrackMetadataResponse,
)
from .metadata_deps import _MetadataDeps, _deps
from .metadata_batch import (
    batch_update_metadata,
)
from .metadata_tracks import (
    get_editable_fields,
    get_track_metadata,
    update_track_metadata,
)

logger = logging.getLogger(__name__)
# Note: router is created inside create_metadata_router() for better testability


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_metadata_router() used to be a ~310-line closure: every handler
# below was nested inside it purely to reach get_repository_factory /
# broadcast_manager / metadata_editor via closure capture, which made a
# handler impossible to import or call without first building the whole
# router. Handlers are now module level; they reach the same callables
# through FastAPI Depends() instead.
#
# Factory calls can coexist in one process (the live app plus throwaway test
# apps), so each router publishes its own deps through a request ContextVar.
# The module-level holder is only the fallback for direct handler calls where
# no router-level dependency ran (#5262).
#
# A handler's Depends() default is only consulted when FastAPI itself
# invokes it for a real request; a direct unit-test call passes the
# dependency explicitly as a keyword argument and never touches
# _MetadataDeps at all -- that's the seam #4670 asked for.
#
# Note the handlers still call require_repository_factory(...) themselves
# rather than receiving an already-resolved RepositoryFactory: the batch
# route deliberately answers an empty `updates` list with a 400 BEFORE it
# ever touches the factory, and resolving the factory in a Depends() would
# turn that into a 503 whenever the factory is unavailable. Injecting the
# getter keeps the original ordering verbatim.
# ============================================================================


def create_metadata_router(
    get_repository_factory: Callable[[], Any],
    broadcast_manager: Any,
    metadata_editor: MetadataEditor | None = None
) -> APIRouter:
    """
    Factory function to create metadata router with dependencies.

    Args:
        get_repository_factory: Callable that returns RepositoryFactory instance
        broadcast_manager: WebSocket broadcast manager
        metadata_editor: Optional MetadataEditor instance (for testing)

    Returns:
        APIRouter: Configured router instance

    Note:
    """
    # Initialize metadata editor (shared instance) or use provided one
    if metadata_editor is None:
        metadata_editor = MetadataEditor()

    deps = _MetadataDeps(get_repository_factory, broadcast_manager, metadata_editor)

    # Create a fresh router instance (important for testing - avoids route pollution)
    router = APIRouter(
        tags=["metadata"],
        dependencies=[Depends(_deps.bind(deps))],
    )

    router.add_api_route("/api/metadata/tracks/{track_id}/fields", get_editable_fields, methods=["GET"], response_model=EditableFieldsResponse)
    router.add_api_route("/api/metadata/tracks/{track_id}", get_track_metadata, methods=["GET"], response_model=TrackMetadataResponse)
    router.add_api_route("/api/metadata/tracks/{track_id}", update_track_metadata, methods=["PUT"], response_model=MetadataUpdateResponse)
    router.add_api_route("/api/metadata/batch", batch_update_metadata, methods=["POST"], response_model=BatchMetadataResponse)

    return router
