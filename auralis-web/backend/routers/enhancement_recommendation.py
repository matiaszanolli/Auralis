"""
GET /api/player/mastering/recommendation/{track_id} handler (split from enhancement.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from cache import streamlined_cache_manager
from cache.models import RECOMMENDATION_THRESHOLD_STEP
from core import audio_stream_controller as _asc
from fastapi import Depends, HTTPException, Path, Query
from schemas import DEFAULT_PRESET
from security.path_errors import PathMissingError, PathValidationError
from security.path_security import validate_file_path
from typing import Annotated, Any
import asyncio

from .dependencies import require_service, with_error_handling
from .enhancement_deps import _get_repository_factory
from .errors import BadRequestError, NotFoundError, UnprocessableAudioFileError

logger = logging.getLogger(__name__)


@with_error_handling("generate mastering recommendation")
async def get_mastering_recommendation(
    track_id: Annotated[int, Path(ge=1)],
    confidence_threshold: float = Query(
        0.4,
        ge=0.0,
        le=1.0,
        description="Threshold for switching from single to blended recommendations",
    ),
    repos: Any = Depends(_get_repository_factory),
) -> dict[str, Any]:
    """
    Get weighted mastering profile recommendation for a track (Priority 4).

    Analyzes the track's audio characteristics and returns single or blended
    profile recommendations based on confidence thresholds.

    The filepath is resolved from the database by track_id to prevent
    mismatched track/file analysis (fixes #2731).

    Args:
        track_id: Track database ID
        confidence_threshold: Threshold for switching from single to blended recommendations (0.0-1.0)

    Returns:
        dict: MasteringRecommendation serialized to JSON with weighted_profiles if hybrid

    Raises:
        HTTPException: 404 if track not found
        HTTPException: 503 if repository unavailable
        HTTPException: 500 if analysis fails
    """
    # Snap to the cache's step so lookup, store and analysis all use one key (#5956).
    confidence_threshold = round(
        round(confidence_threshold / RECOMMENDATION_THRESHOLD_STEP) * RECOMMENDATION_THRESHOLD_STEP, 2
    )

    # Resolve filepath from DB by track_id (fixes #2731)
    repos = require_service(repos, "Repository")

    track = await asyncio.to_thread(repos.tracks.get_by_id, track_id)
    if not track:
        raise NotFoundError("Track", track_id)

    filepath = track.filepath
    if not filepath:
        raise BadRequestError(f"Track {track_id} has no filepath")

    # #4817: re-check the DB-sourced path before any file I/O, as metadata.py
    # does (#2302). Deliberately generic detail: PathValidationError's text
    # names the resolved path and every allowed directory (#4807).
    try:
        filepath = str(await asyncio.to_thread(validate_file_path, str(filepath)))
    except PathMissingError:
        # #5483: a deleted/moved file is "not found", not a bad request —
        # matches the split metadata.py made in #5080.
        raise NotFoundError("Audio file", detail=f"Audio file not found for track {track_id}")
    except PathValidationError:
        raise BadRequestError(f"Track {track_id}'s file is not in an allowed location")

    # Return cached result if still valid — avoids re-running full audio
    # analysis (~1-5 s CPU) on repeated calls for the same track (#3865).
    _cached = streamlined_cache_manager.get_mastering_recommendation(
        track_id, confidence_threshold
    )
    if _cached is not None:
        logger.debug(f"Returning cached mastering recommendation for track {track_id}")
        return _cached

    try:
        from core.chunked_processor import ChunkedAudioProcessor

        # Run CPU-bound processor off the event loop (#2301)
        _fp = str(filepath)
        _tid = track_id
        _ct = confidence_threshold

        def _run_recommendation() -> dict[str, Any] | None:
            proc = ChunkedAudioProcessor(
                track_id=_tid,
                filepath=_fp,
                preset=DEFAULT_PRESET,  # Default for analysis-only mode
                intensity=1.0,
                chunk_cache={}
            )
            rec = proc.get_mastering_recommendation(confidence_threshold=_ct)
            # Use to_response (not to_dict) so the payload carries track_id +
            # is_hybrid and honors MasteringRecommendationResponse (#3840).
            return rec.to_response(_tid) if rec is not None else None

        # #5248: bound the same way every streaming entry point bounds
        # ChunkedAudioProcessor construction — sf.info() has no timeout of
        # its own for natively-decodable formats, so a corrupt header or a
        # track on storage that disappears mid-read can otherwise hang this
        # thread forever and, since analysis is unconditional, eventually
        # exhaust the shared IO_EXECUTOR pool.
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_run_recommendation),
                timeout=_asc.CHUNK_PROCESS_TIMEOUT,
            )
        except TimeoutError:
            # 504 like the scan route's timeout, not a generic 500 (#5997).
            raise HTTPException(
                status_code=504,
                detail="Mastering recommendation analysis timed out — "
                "the file may be corrupt or on slow storage",
            ) from None

        if result is None:
            # None only ever means "this file could not be analysed": the engine
            # itself always has a fallback profile. A client-side file problem,
            # not a server fault (#5997).
            raise UnprocessableAudioFileError()

        result_dict = result if isinstance(result, dict) else {}
        streamlined_cache_manager.set_mastering_recommendation(
            track_id, result_dict, confidence_threshold
        )
        return result_dict

    except HTTPException:
        raise
