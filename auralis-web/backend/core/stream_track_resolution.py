#!/usr/bin/env python3

"""
Streaming Track Lookup + Path Validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The "get track from library, validate its filepath before any file I/O"
block that stream_normal.py, stream_enhanced.py and stream_seek.py each
carried as an identical ~30-line copy (#5032) — the DB-retrieved
`track.filepath` validation guard added by #4345/#2302, extended here to
streaming's highest-traffic consumer of that field.

Deliberately narrow: this is ONLY the lookup+validation block. The
semaphore/cancellation skeleton and the per-chunk streaming loop stay in
each caller — #5032's own proposed fix calls that the highest-regression-risk
part of these handlers, exactly where the prior fix history (#4999, #5074,
#5082, #4790, #4732...) lives, so it is deliberately left untouched.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING, Any

from security.path_security import PathValidationError

if TYPE_CHECKING:
    from . import audio_stream_controller as _asc
    from fastapi import WebSocket

logger = logging.getLogger(__name__)


async def resolve_and_validate_track(
    controller: '_asc.AudioStreamController',
    track_id: int,
    websocket: 'WebSocket',
    *,
    validate_file_path: Any,
) -> tuple[Any, str] | None:
    """Look up ``track_id`` and validate its filepath before any file I/O.

    ``validate_file_path`` is taken as a parameter — deliberately NOT
    imported directly in this module — because each caller's test suite
    patches it as a per-module attribute (``core.stream_normal.validate_file_path``,
    etc., see tests/backend/conftest.py's autouse
    ``_bypass_streaming_path_validation`` fixture). Passing the caller's own
    module-resolved reference here keeps that patch target working exactly
    as it did before this block was shared.

    Returns ``(track, validated_filepath)`` on success. On failure, has
    already sent a clean ``audio_stream_error`` to the client and returns
    ``None`` — the caller should ``return`` immediately.
    """
    try:
        factory = controller._get_repository_factory()
        track = await asyncio.to_thread(factory.tracks.get_by_id, track_id)
        if not track:
            await controller._send_error(websocket, track_id, "Track not found")
            return None

        # Validate the DB-retrieved filepath before any file I/O — mirrors
        # metadata.py's guard (fixes #2302), extended here to streaming's
        # highest-traffic consumer of track.filepath (#4345).
        try:
            validated_filepath = str(
                await asyncio.to_thread(
                    functools.partial(
                        validate_file_path,
                        str(track.filepath),
                        context=f"track {track_id}",
                    )
                )
            )
        except PathValidationError:
            # No logger call here: validate_file_path logs the rejection
            # itself with the context above, exactly once (#4925).
            await controller._send_error(
                websocket, track_id, "Audio file not found"
            )
            return None
    except Exception as e:
        logger.error(f"Failed to load track {track_id}: {e}", exc_info=True)
        await controller._send_error(websocket, track_id, "Failed to load track")
        return None

    return track, validated_filepath
