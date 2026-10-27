"""
Similarity explanation and system-fit handlers (split from similarity.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.analysis.fingerprint import FingerprintSimilarity
from collections.abc import Callable
from fastapi import Depends, Path, Query
from typing import Annotated, Any
import asyncio

from . import dependencies
from .errors import BadRequestError, NotFoundError
from .similarity_common import _with_similarity_error_handling, require_fingerprinted_tracks, require_fitted, require_similarity_system
from .similarity_deps import _get_repository_factory_getter, _get_similarity_system_getter, _repository_factory_getter, _similarity_system_getter
from .similarity_models import EXPLAINABLE_DIMENSIONS, SimilarityExplanation


@_with_similarity_error_handling("Error explaining similarity")
async def explain_similarity(
    track_id1: Annotated[int, Path(ge=1)],
    track_id2: Annotated[int, Path(ge=1)],
    top_n: int = Query(
        5,
        ge=1,
        le=EXPLAINABLE_DIMENSIONS,
        description="Number of top contributing dimensions",
    ),
    get_repository_factory: Annotated[
        Callable[[], Any], Depends(_get_repository_factory_getter)
    ] = _repository_factory_getter,
    get_similarity_system: Annotated[
        Callable[[], FingerprintSimilarity], Depends(_get_similarity_system_getter)
    ] = _similarity_system_getter,
) -> SimilarityExplanation:
    """
    Explain why two tracks are similar/different

    Returns the top dimensions contributing to similarity/difference.

    Args:
        track_id1: First track ID
        track_id2: Second track ID
        top_n: Number of top dimensions to return (1..EXPLAINABLE_DIMENSIONS)

    Returns:
        Detailed explanation of similarity
    """
    repos = dependencies.require_repository_factory(get_repository_factory)

    # #4630: this route had no repository handle at all, so it performed
    # none of the checks its siblings do — a nonexistent track, a track
    # missing a fingerprint, and a genuine engine failure all surfaced as
    # one opaque "Could not generate explanation", and nothing was ever
    # enqueued, so the explain view failed permanently where /similar
    # would have repaired itself.
    await require_fingerprinted_tracks(repos, track_id1, track_id2)

    similarity = await require_fitted(require_similarity_system(get_similarity_system))

    explanation = await asyncio.to_thread(similarity.get_similarity_explanation, track_id1, track_id2, top_n=top_n)

    # Both tracks exist and are fingerprinted by now, so a falsy return no
    # longer means "something, somewhere, was missing" — it means the engine
    # itself could not produce an explanation for this pair.
    if not explanation:
        raise NotFoundError(
            "Explanation",
            detail=(
                f"Similarity engine could not explain tracks {track_id1} "
                f"and {track_id2}"
            ),
        )

    return SimilarityExplanation(**explanation)


@_with_similarity_error_handling("Error fitting similarity system")
async def fit_similarity_system(
    min_samples: int = Query(10, ge=5, description="Minimum fingerprints required to fit"),
    get_repository_factory: Annotated[
        Callable[[], Any], Depends(_get_repository_factory_getter)
    ] = _repository_factory_getter,
    get_similarity_system: Annotated[
        Callable[[], FingerprintSimilarity], Depends(_get_similarity_system_getter)
    ] = _similarity_system_getter,
) -> dict[str, Any]:
    """
    Fit the similarity system with current fingerprints

    The similarity system must be fitted before building the K-NN graph
    or performing similarity searches.

    Args:
        min_samples: Minimum number of fingerprints required

    Returns:
        Status and fitted track count
    """
    repos = dependencies.require_repository_factory(get_repository_factory)
    similarity = require_similarity_system(get_similarity_system)

    # Check if already fitted (and the library has not outgrown that fit, #5716)
    if await asyncio.to_thread(similarity.is_fitted) and not await asyncio.to_thread(
        similarity.needs_refit
    ):
        count = await asyncio.to_thread(repos.fingerprints.get_count, True)
        return {
            "fitted": True,
            "total_fingerprints": count,
            "message": f"Similarity system already fitted with {count} tracks"
        }

    # Count what the fit will read: current-version, non-claim rows (#5716)
    fingerprint_count = await asyncio.to_thread(repos.fingerprints.get_count, True)

    if fingerprint_count < min_samples:
        raise BadRequestError(f"Insufficient fingerprints: {fingerprint_count} < {min_samples}")

    # Fit the similarity system — CPU-bound O(N²); offload to thread
    # so the event loop stays responsive (fixes #2738).
    await asyncio.to_thread(similarity.fit)

    return {
        "fitted": True,
        "total_fingerprints": fingerprint_count,
        "message": f"Successfully fitted similarity system with {fingerprint_count} tracks"
    }
