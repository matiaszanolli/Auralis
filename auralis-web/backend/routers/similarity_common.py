"""
Similarity Router — Shared Error Helpers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Error-handling helpers shared by the similarity router family (similarity
search, similarity graph, fingerprint queue). Extracted from similarity.py
(#4270) so the three routers can live in separate modules without duplicating
the #3331 correlation-id redaction logic.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import functools
import logging
import uuid
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from fastapi import HTTPException

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
