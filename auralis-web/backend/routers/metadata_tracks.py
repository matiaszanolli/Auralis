"""
Single-track metadata handlers: editable fields, read, update (split from metadata.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from auralis.library.metadata_editor import MetadataEditor, UnreadableAudioFileError
from collections.abc import Callable
from fastapi import Depends, HTTPException, Path
from typing import Annotated, Any
from websocket.outbound_messages import broadcast_typed
import asyncio

from . import dependencies
from .dependencies import with_error_handling
from .errors import BadRequestError, NotFoundError, UnprocessableAudioFileError
from .metadata_deps import _get_broadcast_manager, _get_metadata_editor, _get_repository_factory, _tag_dict_to_db_columns, _validate_track_filepath
from .metadata_models import MetadataUpdateRequest

logger = logging.getLogger(__name__)


@with_error_handling("get editable fields")
async def get_editable_fields(
    track_id: Annotated[int, Path(ge=1)],
    get_repository_factory: Callable[[], Any] = Depends(_get_repository_factory),
    metadata_editor: MetadataEditor = Depends(_get_metadata_editor),
) -> dict[str, Any]:
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
        repos = dependencies.require_repository_factory(get_repository_factory)
        # Get track from database
        track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)

        if not track:
            raise NotFoundError("Track")

        # Validate DB-retrieved filepath before any file I/O (fixes #2302).
        # 404 when the file is simply gone, 400 when the path is rejected (#5080).
        filepath_str = await _validate_track_filepath(track_id, track.filepath)
        editable_fields = await asyncio.to_thread(metadata_editor.get_editable_fields, filepath_str)

        # Get current metadata (file I/O — run in thread)
        current_metadata = await asyncio.to_thread(metadata_editor.read_metadata, filepath_str)

        return {
            "track_id": track_id,
            "format": track.format,
            "editable_fields": editable_fields,
            "current_metadata": current_metadata
        }

    except HTTPException:
        raise  # Re-raise HTTPException as-is (don't wrap in 500)
    except FileNotFoundError:
        # The existence check above raises PathMissingError -> 404; this arm
        # covers the remaining race, the file disappearing between validation
        # and the read/write below, and answers it with the same 404.
        raise NotFoundError("Audio file", detail=f"Audio file not found for track {track_id}")
    except UnreadableAudioFileError:
        # Same fixed 422 on every route and extension; never the exception
        # text, which names the file (#5993).
        raise UnprocessableAudioFileError() from None


@with_error_handling("get track metadata")
async def get_track_metadata(
    track_id: Annotated[int, Path(ge=1)],
    get_repository_factory: Callable[[], Any] = Depends(_get_repository_factory),
    metadata_editor: MetadataEditor = Depends(_get_metadata_editor),
) -> dict[str, Any]:
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
        repos = dependencies.require_repository_factory(get_repository_factory)
        # Get track from database
        track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)

        if not track:
            raise NotFoundError("Track")

        # Validate DB-retrieved filepath before file I/O (fixes #2302).
        # 404 when the file is simply gone, 400 when the path is rejected (#5080).
        filepath_validated = await _validate_track_filepath(track_id, track.filepath)

        # Read metadata from file (offloaded to thread to avoid event-loop block, fixes #2317)
        metadata = await asyncio.to_thread(metadata_editor.read_metadata, filepath_validated)

        return {
            "track_id": track_id,
            "format": track.format,
            "metadata": metadata
        }

    except HTTPException:
        raise  # Re-raise HTTPException as-is
    except FileNotFoundError:
        # The existence check above raises PathMissingError -> 404; this arm
        # covers the remaining race, the file disappearing between validation
        # and the read/write below, and answers it with the same 404.
        raise NotFoundError("Audio file", detail=f"Audio file not found for track {track_id}")
    except UnreadableAudioFileError:
        # Same fixed 422 on every route and extension; never the exception
        # text, which names the file (#5993).
        raise UnprocessableAudioFileError() from None


@with_error_handling("update track metadata")
async def update_track_metadata(
    track_id: Annotated[int, Path(ge=1)],
    request: MetadataUpdateRequest,
    get_repository_factory: Callable[[], Any] = Depends(_get_repository_factory),
    metadata_editor: MetadataEditor = Depends(_get_metadata_editor),
    broadcast_manager: Any = Depends(_get_broadcast_manager),
) -> dict[str, Any]:
    """
    Update metadata for a track.

    Args:
        track_id: Track ID
        request: Metadata fields to update

    Returns:
        dict: Updated track metadata

    Raises:
        HTTPException: If track not found, file doesn't exist, or update fails
    """
    try:
        repos = dependencies.require_repository_factory(get_repository_factory)
        # Get track from database
        track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)

        if not track:
            raise NotFoundError("Track")

        # Convert request to dict and filter out None values
        metadata_updates = {
            k: v for k, v in request.model_dump().items()
            if v is not None
        }

        if not metadata_updates:
            raise BadRequestError("No metadata fields provided")

        # Validate DB-retrieved filepath before any file I/O (fixes #2302).
        # 404 when the file is simply gone, 400 when the path is rejected (#5080).
        filepath_validated = await _validate_track_filepath(track_id, track.filepath)

        # Write metadata to file (backup always enforced server-side, fixes #2407).
        # Offloaded to thread to avoid blocking the event loop (fixes #2317).
        success = await asyncio.to_thread(
            metadata_editor.write_metadata,
            filepath_validated,
            metadata_updates,
            True  # backup=True
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to write metadata to file")

        # Update database record using repository. metadata_updates is
        # tag-keyed (matches write_metadata above); translate to DB
        # column names first or track/disc/comment silently vanish (#4731).
        db_metadata_updates = _tag_dict_to_db_columns(metadata_updates)
        updated_track = await asyncio.to_thread(
            lambda: repos.tracks.update_metadata(track_id, **db_metadata_updates)
        )
        if not updated_track:
            raise NotFoundError("Track", detail="Track not found for update")

        # Use the updated track for subsequent operations
        track = updated_track

        # Broadcast metadata updated event. updated_fields lists what was
        # written to the FILE (tag names); fields with no Track DB
        # column (artist, album, albumartist, genre, bpm, composer,
        # publisher, copyright) are intentionally file-only and don't
        # appear in db_metadata_updates above (#4731).
        if broadcast_manager:
            await broadcast_typed(
                broadcast_manager,
                "metadata_updated",
                {
                    "track_id": track_id,
                    "updated_fields": list(metadata_updates.keys()),
                },
            )

        # Read updated metadata (offloaded to thread, fixes #2317)
        # track was refreshed from DB above — re-validate before read (fixes #2302)
        validated_path_for_read = await _validate_track_filepath(track_id, track.filepath)
        updated_metadata = await asyncio.to_thread(metadata_editor.read_metadata, validated_path_for_read)

        logger.info(f"Updated metadata for track {track_id}: {list(metadata_updates.keys())}")

        return {
            "track_id": track_id,
            "success": True,
            "updated_fields": list(metadata_updates.keys()),
            "metadata": updated_metadata
        }

    except HTTPException:
        raise
    except FileNotFoundError:
        # The existence check above raises PathMissingError -> 404; this arm
        # covers the remaining race, the file disappearing between validation
        # and the read/write below, and answers it with the same 404.
        raise NotFoundError("Audio file", detail=f"Audio file not found for track {track_id}")
    except UnreadableAudioFileError:
        # Same fixed 422 on every route and extension; never the exception
        # text, which names the file (#5993).
        raise UnprocessableAudioFileError() from None
    except ValueError as e:
        # Request-value validation only; an unreadable file is the arm above.
        raise BadRequestError(f"Invalid metadata: {e}")
