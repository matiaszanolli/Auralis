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

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging

from auralis.library.metadata_editor import MetadataEditor, MetadataUpdate

logger = logging.getLogger(__name__)
# Note: router is created inside create_metadata_router() for better testability


class MetadataUpdateRequest(BaseModel):
    """Request model for metadata updates"""
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    albumartist: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    track: Optional[int] = None
    disc: Optional[int] = None
    comment: Optional[str] = None
    bpm: Optional[int] = None
    composer: Optional[str] = None
    publisher: Optional[str] = None
    lyrics: Optional[str] = None
    copyright: Optional[str] = None

    class Config:
        extra = "forbid"  # Don't allow unknown fields


class BatchMetadataUpdateRequest(BaseModel):
    """Request model for batch metadata updates"""
    track_id: int = Field(..., description="Track ID")
    metadata: Dict[str, Any] = Field(..., description="Metadata fields to update")


class BatchMetadataRequest(BaseModel):
    """Request model for batch update endpoint"""
    updates: List[BatchMetadataUpdateRequest] = Field(..., description="List of updates")
    backup: bool = Field(True, description="Create backup before modification")


def create_metadata_router(get_library_manager, broadcast_manager, metadata_editor=None):
    """
    Factory function to create metadata router with dependencies.

    Args:
        get_library_manager: Callable that returns LibraryManager instance
        broadcast_manager: WebSocket broadcast manager
        metadata_editor: Optional MetadataEditor instance (for testing)

    Returns:
        APIRouter: Configured router instance
    """

    # Create a fresh router instance (important for testing - avoids route pollution)
    router = APIRouter(tags=["metadata"])

    # Initialize metadata editor (shared instance) or use provided one
    if metadata_editor is None:
        metadata_editor = MetadataEditor()

    @router.get("/api/metadata/tracks/{track_id}/fields")
    async def get_editable_fields(track_id: int):
        """
        Get list of editable metadata fields for a track.

        Args:
            track_id: Track ID

        Returns:
            dict: List of editable fields and their current values

        Raises:
            HTTPException: If track not found or file doesn't exist
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            # Get track from database
            from auralis.library.repositories import TrackRepository
            track_repo = TrackRepository(library_manager.SessionLocal)
            track = track_repo.get_by_id(track_id)

            if not track:
                raise HTTPException(status_code=404, detail="Track not found")

            # Get editable fields for this file format
            editable_fields = metadata_editor.get_editable_fields(track.filepath)

            # Get current metadata
            current_metadata = metadata_editor.read_metadata(track.filepath)

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
    async def get_track_metadata(track_id: int):
        """
        Get current metadata for a track.

        Args:
            track_id: Track ID

        Returns:
            dict: Track metadata

        Raises:
            HTTPException: If track not found or file doesn't exist
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            # Get track from database
            from auralis.library.repositories import TrackRepository
            track_repo = TrackRepository(library_manager.SessionLocal)
            track = track_repo.get_by_id(track_id)

            if not track:
                raise HTTPException(status_code=404, detail="Track not found")

            # Read metadata from file
            metadata = metadata_editor.read_metadata(track.filepath)

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
    async def update_track_metadata(track_id: int, request: MetadataUpdateRequest, backup: bool = True):
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
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        try:
            # Get track from database
            from auralis.library.repositories import TrackRepository
            track_repo = TrackRepository(library_manager.SessionLocal)
            track = track_repo.get_by_id(track_id)

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
                track.filepath,
                metadata_updates,
                backup=backup
            )

            if not success:
                raise HTTPException(status_code=500, detail="Failed to write metadata to file")

            # Update database record in the existing session
            for field, value in metadata_updates.items():
                if hasattr(track, field):
                    setattr(track, field, value)

            # The track is already in the session, just need to flush/commit
            # Get the session that contains the track
            from sqlalchemy.orm import object_session, Session
            session = object_session(track)
            # Only use it if it's a real SQLAlchemy Session, not a Mock
            if isinstance(session, Session):
                session.commit()
            else:
                # Fallback to library manager session
                library_manager.session.commit()

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
            updated_metadata = metadata_editor.read_metadata(track.filepath)

            logger.info(f"Updated metadata for track {track_id}: {list(metadata_updates.keys())}")

            return {
                "track_id": track_id,
                "success": True,
                "updated_fields": list(metadata_updates.keys()),
                "metadata": updated_metadata
            }

        except HTTPException:
            # Rollback on HTTP exceptions that indicate failure
            if hasattr(library_manager, 'session') and hasattr(library_manager.session, 'rollback'):
                library_manager.session.rollback()
            raise
        except FileNotFoundError as e:
            # Rollback on file not found
            if hasattr(library_manager, 'session') and hasattr(library_manager.session, 'rollback'):
                library_manager.session.rollback()
            raise HTTPException(status_code=404, detail=f"Audio file not found: {e}")
        except ValueError as e:
            # Rollback on invalid metadata
            if hasattr(library_manager, 'session') and hasattr(library_manager.session, 'rollback'):
                library_manager.session.rollback()
            raise HTTPException(status_code=400, detail=f"Invalid metadata: {e}")
        except Exception as e:
            # Rollback on any other exception
            if hasattr(library_manager, 'session') and hasattr(library_manager.session, 'rollback'):
                library_manager.session.rollback()
            logger.error(f"Failed to update metadata for track {track_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update metadata: {e}")

    @router.post("/api/metadata/batch")
    async def batch_update_metadata(request: BatchMetadataRequest):
        """
        Batch update metadata for multiple tracks.

        Args:
            request: List of metadata updates

        Returns:
            dict: Batch update results (success/failure per track)

        Raises:
            HTTPException: If library manager not available or validation fails
        """
        library_manager = get_library_manager()
        if not library_manager:
            raise HTTPException(status_code=503, detail="Library manager not available")

        if not request.updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        try:
            from auralis.library.repositories import TrackRepository
            track_repo = TrackRepository(library_manager.SessionLocal)

            # Prepare batch updates
            batch_updates = []
            track_map = {}  # Map track_id to track object

            for update_req in request.updates:
                track = track_repo.get_by_id(update_req.track_id)
                if not track:
                    logger.warning(f"Track {update_req.track_id} not found, skipping")
                    continue

                track_map[update_req.track_id] = track

                batch_updates.append(MetadataUpdate(
                    track_id=update_req.track_id,
                    filepath=track.filepath,
                    updates=update_req.metadata,
                    backup=request.backup
                ))

            # Execute batch update
            results = metadata_editor.batch_update(batch_updates)

            # Update database for successful updates
            successful_track_ids = []
            from sqlalchemy.orm import object_session, Session
            session = None

            for result in results.get('results', []):
                if result['success']:
                    track_id = result['track_id']
                    track = track_map.get(track_id)

                    if track:
                        # Update database record
                        for field, value in result.get('updates', {}).items():
                            if hasattr(track, field):
                                setattr(track, field, value)
                        successful_track_ids.append(track_id)

                        # Get session from the track object (same session as when loaded)
                        if session is None:
                            obj_session = object_session(track)
                            # Only use it if it's a real SQLAlchemy Session, not a Mock
                            if isinstance(obj_session, Session):
                                session = obj_session

            if successful_track_ids:
                if session and isinstance(session, Session):
                    session.commit()
                else:
                    # Fallback to library manager session
                    library_manager.session.commit()

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
            # Rollback on any exception
            try:
                library_manager.session.rollback()
            except:
                pass
            logger.error(f"Batch metadata update failed: {e}")
            raise HTTPException(status_code=500, detail=f"Batch update failed: {e}")

    return router
