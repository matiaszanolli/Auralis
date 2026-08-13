"""
Similarity Router — Shared Error Helpers and Preconditions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Error-handling helpers shared by the similarity router family (similarity
search, similarity graph, fingerprint queue). Extracted from similarity.py
(#4270) so the three routers can live in separate modules without duplicating
the #3331 correlation-id redaction logic.

Also owns the *preconditions* every fingerprint-comparison route needs — that
each track exists and has a fingerprint (#4630). Those checks used to be
open-coded per route, which is how the three routes ended up with three
different policies: `/similar` validated and enqueued, `/compare` validated but
never enqueued, and `/explain` did neither, collapsing "no such track", "no
fingerprint on either side" and "engine failed" into one opaque 404.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import functools
import logging
import uuid
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from fastapi import HTTPException

from .errors import NotFoundError

# Stable logger name shared across the similarity router family so
# correlation-id log records stay under "routers.similarity" no matter which
# module raised them (kept for #3331 log-matching and its tests).
logger = logging.getLogger("routers.similarity")

P = ParamSpec("P")
T = TypeVar("T")


def _internal_error_response(user_message: str, exc: BaseException) -> HTTPException:
    """Log the full exception server-side; return a generic HTTPException.

    Generates a short correlation id so a user-reported failure can be
    matched to its server-side log entry without exposing `str(exc)` —
    which may contain file paths, SQL fragments, dependency versions, or
    other internals — back to the API caller (#3331).
    """
    ref = uuid.uuid4().hex[:8]
    logger.exception("[similarity:%s] %s", ref, user_message, exc_info=exc)
    return HTTPException(status_code=500, detail=f"{user_message} (ref {ref})")


def require_similarity_system(get_similarity_system: Callable[[], T | None]) -> T:
    """Validate that the similarity system is available.

    `config/startup.py` sets ``globals_dict['similarity_system'] = None`` when
    initialisation fails, and the similarity router family is registered on the
    import-time ``HAS_SIMILARITY`` flag independently of whether that init
    succeeded — so ``None`` is reachable at request time. Dereferencing it
    raised ``AttributeError``, which the error decorator turned into an opaque
    500 that a client cannot distinguish from a genuine fault (#4656).

    Mirrors `routers.dependencies.require_repository_factory`.

    Args:
        get_similarity_system: Callable returning the similarity system or None

    Returns:
        The similarity system instance

    Raises:
        HTTPException: 503 if the similarity system is not available
    """
    similarity = get_similarity_system()
    if similarity is None:
        raise HTTPException(
            status_code=503,
            detail="Similarity system not available. Please wait for initialization."
        )
    return similarity


def _with_similarity_error_handling(operation: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator standardizing error handling for the similarity routers.

    Mirrors `routers.dependencies.with_error_handling`, but routes unexpected
    exceptions through `_internal_error_response()` instead of
    `handle_query_error()` so the #3331 correlation-id behavior (no raw
    exception detail leaked to callers) is preserved for these routers.
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await func(*args, **kwargs)  # type: ignore[misc, no-any-return]
            except HTTPException:
                raise
            except Exception as e:
                raise _internal_error_response(operation, e) from e
        return wrapper  # type: ignore[return-value]
    return decorator


async def enqueue_for_fingerprinting(track_id: int) -> bool:
    """Best-effort: queue `track_id` for background fingerprint extraction.

    This is what makes a missing-fingerprint 404 self-healing — the next request
    for the same track succeeds instead of failing forever. It must never be the
    reason a request fails, so every failure path (queue not yet constructed,
    import unavailable in a trimmed test app, enqueue raising) is swallowed and
    logged at debug.

    Returns:
        True if the track was handed to the queue.
    """
    try:
        from analysis.fingerprint_queue import get_fingerprint_queue

        queue = get_fingerprint_queue()
        if queue is None:
            return False
        await asyncio.to_thread(queue.enqueue, track_id)
    except Exception as q_err:  # noqa: BLE001 - never fail the request over this
        logger.debug("Could not enqueue track %s for fingerprinting: %s", track_id, q_err)
        return False

    logger.info("📋 Track %s queued for background fingerprinting", track_id)
    return True


async def require_fingerprinted_tracks(repos: Any, *track_ids: int) -> None:
    """Assert every `track_id` exists and has a fingerprint, or raise a 404.

    Distinguishes the two failure causes, naming the specific offending track in
    each case, and enqueues any track that exists but has no fingerprint so the
    condition repairs itself (#4630).

    Existence is checked for *all* ids before any fingerprint is checked, so
    "track 7 doesn't exist" is never reported as "track 7 has no fingerprint" —
    a nonexistent track trivially has no fingerprint, and reporting the weaker
    cause first would send the caller looking for a queue entry that will never
    be created.

    Args:
        repos: Repository factory exposing `.tracks` and `.fingerprints`.
        *track_ids: One or more track ids, checked in the order given.

    Raises:
        NotFoundError: 404 naming the missing track, or the track whose
            fingerprint is missing.
    """
    for track_id in track_ids:
        if not await asyncio.to_thread(repos.tracks.get_by_id, track_id):
            raise NotFoundError("Track", track_id)

    for track_id in track_ids:
        if not await asyncio.to_thread(repos.fingerprints.exists, track_id):
            await enqueue_for_fingerprinting(track_id)
            raise NotFoundError(
                "Track",
                detail=(
                    f"Track {track_id} does not have a fingerprint. "
                    "Queued for background processing."
                ),
            )
