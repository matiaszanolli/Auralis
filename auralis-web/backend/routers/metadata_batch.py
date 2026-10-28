"""
POST /api/metadata/batch handler (split from metadata.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from auralis.library.metadata_editor import MetadataEditor, MetadataUpdate
from collections.abc import Callable
from fastapi import Depends
from security.path_errors import PathValidationError
from security.path_security import validate_file_path
from typing import Any
from websocket.outbound_messages import broadcast_typed
import asyncio

from . import dependencies
from .dependencies import with_error_handling
from .errors import BadRequestError
from .metadata_deps import _get_broadcast_manager, _get_metadata_editor, _get_repository_factory, _tag_dict_to_db_columns
from .metadata_models import BatchMetadataRequest

logger = logging.getLogger(__name__)


@with_error_handling("batch update metadata")
async def batch_update_metadata(
    request: BatchMetadataRequest,
    get_repository_factory: Callable[[], Any] = Depends(_get_repository_factory),
    metadata_editor: MetadataEditor = Depends(_get_metadata_editor),
    broadcast_manager: Any = Depends(_get_broadcast_manager),
) -> dict[str, Any]:
    """
    Batch update metadata for multiple tracks.

    Args:
        request: List of metadata updates

    Returns:
        dict: Batch update results (success/failure per track)

    Raises:
        HTTPException: If the library is not available or validation fails
    """
    if not request.updates:
        raise BadRequestError("No updates provided")

    repos = dependencies.require_repository_factory(get_repository_factory)

    # Fetch all requested tracks in one WHERE-IN query (fixes #3857 N+1).
    all_track_ids = [u.track_id for u in request.updates]
    track_map: dict[int, Any] = await asyncio.to_thread(
        repos.tracks.get_by_ids, all_track_ids
    )

    # Prepare batch updates — validate filepath for each found track.
    batch_updates = []
    skipped = 0  # requested but never attempted: unknown track, no fields, bad path (#5265)
    for update_req in request.updates:
        track = track_map.get(update_req.track_id)
        if not track:
            logger.warning(f"Track {update_req.track_id} not found, skipping")
            skipped += 1
            continue

        # Drop unset fields, mirroring the single-track route (#4555).
        # model_dump() emits field names (track/disc), not the
        # track_number/disc_number aliases, so both routes hand the
        # metadata editor an identically-shaped tag dict.
        metadata_fields = {
            k: v for k, v in update_req.metadata.model_dump().items()
            if v is not None
        }
        if not metadata_fields:
            logger.warning(
                f"No metadata fields for track {update_req.track_id}, skipping"
            )
            skipped += 1
            continue

        # Validate DB-retrieved filepath before file I/O (fixes #2302)
        try:
            validated_filepath = str(await asyncio.to_thread(
                validate_file_path,
                str(track.filepath),
                context=f"track {update_req.track_id}, batch update — skipping",
            ))
        except PathValidationError:
            # validate_file_path logs it once with the context above (#4925).
            skipped += 1
            continue

        batch_updates.append(MetadataUpdate(
            track_id=update_req.track_id,
            filepath=validated_filepath,
            updates=metadata_fields,
            backup=True  # always enforced server-side (fixes #2407)
        ))

    # Execute batch update (atomic when backup=True).
    # Offloaded to thread to avoid blocking the event loop (fixes #2317).
    results = await asyncio.to_thread(metadata_editor.batch_update, batch_updates)
    rolled_back: bool = results.get('rolled_back', False)

    # Update database for all successful results in one transaction
    # (fixes #3857 N+1 on the update side).
    successful_track_ids = []

    if not rolled_back:
        db_updates: list[tuple[int, dict[str, Any]]] = []
        for result in results.get('results', []):
            if result.get('success'):
                track_id = result['track_id']
                # updates is tag-keyed (echoed from the MetadataUpdate we
                # built above) — translate before the DB write, mirroring
                # the single-track route's fix (#4731).
                updates = _tag_dict_to_db_columns(result.get('updates', {}))
                if updates:
                    db_updates.append((track_id, updates))

        if db_updates:
            successful_track_ids = await asyncio.to_thread(
                repos.tracks.update_metadata_batch, db_updates
            )

    # Broadcast batch update event
    if broadcast_manager and successful_track_ids:
        await broadcast_typed(
            broadcast_manager,
            "metadata_batch_updated",
            {
                "track_ids": successful_track_ids,
                "count": len(successful_track_ids),
            },
        )

    logger.info(
        f"Batch metadata update: {results['successful']}/{results['total']} successful"
        + (", rolled back" if rolled_back else "")
    )

    return {
        # Nothing attempted is not a success: with every request skipped,
        # batch_update([]) reports total=0, failed=0, which read as success (#5265).
        "success": results['failed'] == 0 and not (results['total'] == 0 and skipped > 0),
        "total": results['total'],
        "successful": results['successful'],
        "failed": results['failed'],
        "skipped": skipped,
        "results": results['results'],
        "rolled_back": rolled_back,
    }
