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
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from auralis.library.metadata_editor import MetadataEditor, MetadataUpdate

from .dependencies import require_repository_factory

logger = logging.getLogger(__name__)
# Note: router is created inside create_metadata_router() for better testability


class MetadataUpdateRequest(BaseModel):
    """Request model for metadata updates"""
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    albumartist: str | None = None
    year: int | None = None
    genre: str | None = None
    track: int | None = None
    disc: int | None = None
    comment: str | None = None
    bpm: int | None = None
    composer: str | None = None
    publisher: str | None = None
    lyrics: str | None = None
    copyright: str | None = None

    class Config:
        extra = "forbid"  # Don't allow unknown fields


class BatchMetadataUpdateRequest(BaseModel):
    """Request model for batch metadata updates"""
    track_id: int = Field(..., description="Track ID")
    metadata: dict[str, Any] = Field(..., description="Metadata fields to update")


class BatchMetadataRequest(BaseModel):
    """Request model for batch update endpoint"""
    updates: list[BatchMetadataUpdateRequest] = Field(..., description="List of updates")
    backup: bool = Field(True, description="Create backup before modification")


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
        Phase 6B: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback).
    """

    # Create a fresh router instance (important for testing - avoids route pollution)
    router = APIRouter(tags=["metadata"])

    # Initialize metadata editor (shared instance) or use provided one
    if metadata_editor is None:
        metadata_editor = MetadataEditor()

    @router.get("/api/metadata/tracks/{track_id}/fields")
    async def get_editable_fields(track_id: int) -> dict[str, Any]:
        """
        Get list of editable metadata fields for a track.

        Args:
            track_id: Track ID

        Returns:
            dict: List of editable fields and their current values

        Raises:
            HTTPException: If track not found or file doesn't exist
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            # Get track from database
            track = repos.tracks.get_by_id(track_id)

            if not track:
                raise HTTPException(status_code=404, detail="Track not found")

            # Get editable fields for this file format
            editable_fields = metadata_editor.get_editable_fields(str(track.filepath))

            # Get current metadata
            current_metadata = metadata_editor.read_metadata(str(track.filepath))

            return {
                "track_id": track_id,
                "filepath": track.filepath,
                "format": track.format,
                "editable_fields": editable_fields,
                "current_metadata": current_metadata
            }

        except HTTPException:
            raise  # Re-raise HTTPException as-is (don't wrap in 500)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"Audio file not found: {e}")
        except Exception as e:
            logger.error(f"Failed to get editable fields for track {track_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get editable fields: {e}")

    @router.get("/api/metadata/tracks/{track_id}")
    async def get_track_metadata(track_id: int) -> dict[str, Any]:
        """
        Get current metadata for a track.

        Args:
            track_id: Track ID

        Returns:
            dict: Track metadata

        Raises:
            HTTPException: If track not found or file doesn't exist
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            # Get track from database
            track = repos.tracks.get_by_id(track_id)

            if not track:
                raise HTTPException(status_code=404, detail="Track not found")

            # Read metadata from file
            metadata = metadata_editor.read_metadata(str(track.filepath))

            return {
                "track_id": track_id,
                "filepath": track.filepath,
                "format": track.format,
                "metadata": metadata
            }

        except HTTPException:
            raise  # Re-raise HTTPException as-is
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"Audio file not found: {e}")
        except Exception as e:
            logger.error(f"Failed to get metadata for track {track_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get metadata: {e}")

    @router.put("/api/metadata/tracks/{track_id}")
    async def update_track_metadata(track_id: int, request: MetadataUpdateRequest, backup: bool = True) -> dict[str, Any]:
        """
        Update metadata for a track.

        Args:
            track_id: Track ID
            request: Metadata fields to update
            backup: Create backup before modification (default: True)

        Returns:
            dict: Updated track metadata

        Raises:
            HTTPException: If track not found, file doesn't exist, or update fails
        """
        try:
            repos = require_repository_factory(get_repository_factory)
            # Get track from database
            track = repos.tracks.get_by_id(track_id)

            if not track:
                raise HTTPException(status_code=404, detail="Track not found")

            # Convert request to dict and filter out None values
            metadata_updates = {
                k: v for k, v in request.model_dump().items()
                if v is not None
            }

            if not metadata_updates:
                raise HTTPException(status_code=400, detail="No metadata fields provided")

            # Write metadata to file
            success = metadata_editor.write_metadata(
                str(track.filepath),
                metadata_updates,
                backup=backup
            )

            if not success:
                raise HTTPException(status_code=500, detail="Failed to write metadata to file")

            # Update database record using repository
            updated_track = repos.tracks.update_metadata(track_id, **metadata_updates)
            if not updated_track:
                raise HTTPException(status_code=404, detail="Track not found for update")

            # Use the updated track for subsequent operations
            track = updated_track

            # Broadcast metadata updated event
            if broadcast_manager:
                await broadcast_manager.broadcast({
                    "type": "metadata_updated",
                    "data": {
                        "track_id": track_id,
                        "updated_fields": list(metadata_updates.keys())
                    }
                })

            # Read updated metadata
            updated_metadata = metadata_editor.read_metadata(str(track.filepath))

            logger.info(f"Updated metadata for track {track_id}: {list(metadata_updates.keys())}")

            return {
                "track_id": track_id,
                "success": True,
                "updated_fields": list(metadata_updates.keys()),
                "metadata": updated_metadata
            }

        except HTTPException:
            raise
        except FileNotFoundError as e:
            # File not found error
            raise HTTPException(status_code=404, detail=f"Audio file not found: {e}")
        except ValueError as e:
            # Invalid metadata error
            raise HTTPException(status_code=400, detail=f"Invalid metadata: {e}")
        except Exception as e:
            logger.error(f"Failed to update metadata for track {track_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update metadata: {e}")

    @router.post("/api/metadata/batch")
    async def batch_update_metadata(request: BatchMetadataRequest) -> dict[str, Any]:
        """
        Batch update metadata for multiple tracks.

        Args:
            request: List of metadata updates

        Returns:
            dict: Batch update results (success/failure per track)

        Raises:
            HTTPException: If library manager/factory not available or validation fails
        """
        if not request.updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        try:
            repos = require_repository_factory(get_repository_factory)

            # Prepare batch updates
            batch_updates = []
            track_map = {}  # Map track_id to track object

            for update_req in request.updates:
                track = repos.tracks.get_by_id(update_req.track_id)
                if not track:
                    logger.warning(f"Track {update_req.track_id} not found, skipping")
                    continue

                track_map[update_req.track_id] = track

                batch_updates.append(MetadataUpdate(
                    track_id=update_req.track_id,
                    filepath=str(track.filepath),
                    updates=update_req.metadata,
                    backup=request.backup
                ))

            # Execute batch update
            results = metadata_editor.batch_update(batch_updates)

            # Update database for successful updates using repository
            successful_track_ids = []

            for result in results.get('results', []):
                if result['success']:
                    track_id = result['track_id']
                    updates = result.get('updates', {})

                    if updates:
                        # Update database record using repository
                        updated_track = repos.tracks.update_metadata(track_id, **updates)
                        if updated_track:
                            successful_track_ids.append(track_id)

            # Broadcast batch update event
            if broadcast_manager and successful_track_ids:
                await broadcast_manager.broadcast({
                    "type": "metadata_batch_updated",
                    "data": {
                        "track_ids": successful_track_ids,
                        "count": len(successful_track_ids)
                    }
                })

            logger.info(
                f"Batch metadata update: {results['successful']}/{results['total']} successful"
            )

            return {
                "success": True,
                "total": results['total'],
                "successful": results['successful'],
                "failed": results['failed'],
                "results": results['results']
            }

        except Exception as e:
            logger.error(f"Batch metadata update failed: {e}")
            raise HTTPException(status_code=500, detail=f"Batch update failed: {e}")

    return router
