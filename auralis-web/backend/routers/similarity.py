"""
Similarity API Router
~~~~~~~~~~~~~~~~~~~~

REST API endpoints for fingerprint-based music similarity

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
from contextvars import ContextVar
from typing import Annotated, Any
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from .errors import NotFoundError
from pydantic import BaseModel, Field

from auralis.analysis.fingerprint import (
    FingerprintNormalizer,
    FingerprintSimilarity,
    KNNGraphBuilder,
    SimilarityResult,
)

# Upper bound for `top_n` on the explain route. Derived from the dimension list
# the explanation actually slices — `DistanceCalculator.get_dimension_contributions()`
# enumerates `FingerprintNormalizer.DIMENSION_NAMES` — rather than hard-coded to
# today's count, so extending the fingerprint vector cannot leave the API
# silently refusing dimensions that exist (#4630).
EXPLAINABLE_DIMENSIONS = len(FingerprintNormalizer.DIMENSION_NAMES)

from .dependencies import require_repository_factory
# Shared error helpers live in similarity_common (#4270) so the similarity-graph
# and fingerprint-queue routers can reuse them. Re-exported here for backward
# compatibility (e.g. tests importing routers.similarity._internal_error_response).
from .similarity_common import (  # noqa: F401
    _internal_error_response,
    _with_similarity_error_handling,
    require_fingerprinted_tracks,
    require_similarity_system,
)

class FitSimilarityResponse(BaseModel):
    """Result of fitting the similarity system.

    Returned unchanged when the system was already fitted — `fitted` is True
    in both branches; only `message` distinguishes them.
    """
    fitted: bool = Field(description="True once the system is fitted")
    total_fingerprints: int = Field(description="Fingerprints the system was fitted on")
    message: str = Field(description="Human-readable summary")



# Response models
class SimilarTrack(BaseModel):
    """Similar track response model"""
    track_id: int = Field(..., description="ID of the similar track")
    distance: float = Field(..., description="Fingerprint distance (lower = more similar)")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score 0-1 (higher = more similar)")
    rank: int | None = Field(None, description="Rank in similarity (1=most similar)")

    # Optional track details
    title: str | None = None
    artist: str | None = None
    album: str | None = None


class ComparisonResult(BaseModel):
    """Pairwise comparison of two specific tracks."""
    track_id1: int = Field(..., description="First track ID")
    track_id2: int = Field(..., description="Second track ID")
    distance: float = Field(..., description="Fingerprint distance (lower = more similar)")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score 0-1")


class DimensionContribution(BaseModel):
    """A single fingerprint dimension's contribution to the distance.

    value1/value2/difference are the raw (denormalized) per-track values and
    are optional so a partial engine payload never fails validation (#4415).
    """
    dimension: str
    contribution: float
    value1: float | None = None
    value2: float | None = None
    difference: float | None = None


class SimilarityExplanation(BaseModel):
    """Detailed similarity explanation"""
    track_id1: int
    track_id2: int
    distance: float
    similarity_score: float
    # Both are arrays of DimensionContribution (#4415/#4416): top_differences
    # is the top-N by contribution, all_contributions is every dimension.
    top_differences: list[DimensionContribution]
    all_contributions: list[DimensionContribution]


# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_similarity_router() used to be one 260-line closure: every handler
# below was a nested `async def` that existed only to reach
# get_similarity_system / get_graph_builder / get_repository_factory by
# closure capture, which made a handler impossible to import or call without
# first building the whole router. The handlers are now module level and reach
# the same three callables through FastAPI Depends().
#
# What is injected is the *getter*, not the resolved object, because the
# resolution points are load-bearing: `/similar` only requires a similarity
# system on the real-time fallback path, and `/compare` and `/explain` resolve
# it only after their 404 preconditions have passed. Injecting resolved
# objects would turn those into unconditional dependency-resolution failures
# and change 404s into 503s.
#
# Unlike routers/player.py's _PlayerDeps, this factory genuinely does run more
# than once per process: several test modules build a throwaway router over
# mocks while `main.app`'s router is already live in the same interpreter. So
# the deps are bound *per router* — each router carries a router-level
# dependency that publishes its own _SimilarityDeps into a ContextVar for the
# duration of the request — instead of relying on a single module-level holder
# that the next factory call would silently clobber. The module-level
# `_deps` is only the fallback for a *direct* call to a handler, where no
# request (and therefore no ContextVar binding) exists.
#
# A handler's Depends()-annotated parameter also carries a plain default, so a
# direct unit-test call needs no arguments at all — and a caller that wants
# full isolation passes its own getter as a keyword argument, touching neither
# Depends() nor _SimilarityDeps. That's the seam #4670 asked for.
# ============================================================================

def _unavailable() -> Any:
    """Placeholder getter used before any router has been built."""
    return None


class _SimilarityDeps:
    """The three callables create_similarity_router() receives."""

    def __init__(
        self,
        get_similarity_system: Callable[[], FingerprintSimilarity] = _unavailable,
        get_graph_builder: Callable[[], KNNGraphBuilder | None] = _unavailable,
        get_repository_factory: Callable[[], Any] = _unavailable,
    ) -> None:
        self.get_similarity_system = get_similarity_system
        self.get_graph_builder = get_graph_builder
        self.get_repository_factory = get_repository_factory


# Fallback for direct (non-request) handler calls: the most recently built
# router's dependencies.
_deps = _SimilarityDeps()

# Per-request binding, published by each router's own binder below.
_active_deps: ContextVar[_SimilarityDeps | None] = ContextVar("_active_deps", default=None)


def _current_deps() -> _SimilarityDeps:
    """The deps of the router serving this request, or the last built one."""
    return _active_deps.get() or _deps


def _make_deps_binder(deps: _SimilarityDeps) -> Callable[[], Any]:
    """Build the router-level dependency that publishes `deps` for a request.

    Must be async: a sync dependency is run in a worker thread, which gets a
    *copy* of the context, so the ContextVar set would not be visible to the
    handler.
    """
    async def _bind_similarity_deps() -> None:
        _active_deps.set(deps)

    return _bind_similarity_deps


def _similarity_system_getter() -> FingerprintSimilarity:
    return _current_deps().get_similarity_system()


def _graph_builder_getter() -> KNNGraphBuilder | None:
    return _current_deps().get_graph_builder()


def _repository_factory_getter() -> Any:
    return _current_deps().get_repository_factory()


def _get_similarity_system_getter() -> Callable[[], FingerprintSimilarity]:
    """Depends() provider handing the handler the live similarity-system getter."""
    return _similarity_system_getter


def _get_graph_builder_getter() -> Callable[[], KNNGraphBuilder | None]:
    """Depends() provider handing the handler the live graph-builder getter."""
    return _graph_builder_getter


def _get_repository_factory_getter() -> Callable[[], Any]:
    """Depends() provider handing the handler the live repository-factory getter."""
    return _repository_factory_getter


@_with_similarity_error_handling("Error finding similar tracks")
async def get_similar_tracks(
    track_id: int,
    limit: int = Query(10, ge=1, le=100, description="Number of similar tracks to return"),
    use_graph: bool = Query(True, description="Use pre-computed graph if available"),
    include_details: bool = Query(True, description="Include track title/artist/album"),
    get_repository_factory: Annotated[
        Callable[[], Any], Depends(_get_repository_factory_getter)
    ] = _repository_factory_getter,
    get_graph_builder: Annotated[
        Callable[[], KNNGraphBuilder | None], Depends(_get_graph_builder_getter)
    ] = _graph_builder_getter,
    get_similarity_system: Annotated[
        Callable[[], FingerprintSimilarity], Depends(_get_similarity_system_getter)
    ] = _similarity_system_getter,
) -> list[SimilarTrack]:
    """
    Get similar tracks to a given track

    Uses fingerprint-based similarity to find acoustically similar tracks,
    enabling cross-genre music discovery.

    Args:
        track_id: ID of the target track
        limit: Maximum number of similar tracks (1-100)
        use_graph: Use pre-computed K-NN graph if available (faster)
        include_details: Include track metadata in response

    Returns:
        List of similar tracks sorted by similarity (most similar first)
    """
    repos = require_repository_factory(get_repository_factory)

    # Track must exist and have a fingerprint; a missing fingerprint is
    # enqueued so the next request succeeds (#4630 — shared with /compare
    # and /explain so the three routes cannot drift apart again).
    await require_fingerprinted_tracks(repos, track_id)

    results = []

    # Try to use pre-computed graph if available
    graph_builder = get_graph_builder() if use_graph else None
    if graph_builder is not None:
        neighbors = await asyncio.to_thread(graph_builder.get_neighbors, track_id, limit=limit)

        # The graph stores a fixed `k` edges per track, chosen at build time
        # (`POST /graph/build?k=...`, default 10). `get_neighbors` caps that
        # list at `limit` but cannot extend it, so a request for more than
        # `k` used to return however many the graph happened to hold — with
        # nothing to distinguish "the library only has this many similar
        # tracks" from "the graph was not built wide enough" (#4864).
        #
        # A short list therefore means the graph cannot answer this request,
        # which is the same situation as an empty one: fall back. The count
        # is already in hand, so this costs no extra query, and the fast
        # path still covers the common case where `limit <= k` (the router
        # and the builder share a default of 10). When the library genuinely
        # holds fewer than `limit` similar tracks the fallback returns the
        # same short list — a redundant search over a library small enough
        # for that to be cheap, in exchange for never silently under-serving
        # a wide request.
        if len(neighbors) >= limit:
            # Convert to SimilarTrack objects
            for neighbor in neighbors:
                results.append(SimilarTrack(
                    track_id=neighbor['similar_track_id'],
                    distance=neighbor['distance'],
                    similarity_score=neighbor['similarity_score'],
                    rank=neighbor['rank']
                ))
        else:
            # Graph absent or narrower than the request — recompute.
            graph_builder = None

    if graph_builder is None:
        # Real-time calculation (slower but always available)
        similarity = require_similarity_system(get_similarity_system)

        if not await asyncio.to_thread(similarity.is_fitted):
            raise HTTPException(
                status_code=503,
                detail="Similarity system not initialized. Please wait for initialization."
            )

        similarity_results: list[SimilarityResult] = await asyncio.to_thread(similarity.find_similar, track_id, n=limit)

        for i, sim_result in enumerate(similarity_results, start=1):
            results.append(SimilarTrack(
                track_id=sim_result.track_id,
                distance=sim_result.distance,
                similarity_score=sim_result.similarity_score,
                rank=i
            ))

    # Batch-fetch track details in a single WHERE IN query (#3228)
    if include_details and results:
        track_ids = [r.track_id for r in results]
        tracks_map = await asyncio.to_thread(repos.tracks.get_by_ids, track_ids)
        for r in results:
            t = tracks_map.get(r.track_id)
            if t:
                r.title = t.title
                r.artist = t.artists[0].name if t.artists else None
                r.album = t.album.title if t.album else None

    return results


@_with_similarity_error_handling("Error comparing tracks")
async def compare_tracks(
    track_id1: int,
    track_id2: int,
    get_repository_factory: Annotated[
        Callable[[], Any], Depends(_get_repository_factory_getter)
    ] = _repository_factory_getter,
    get_similarity_system: Annotated[
        Callable[[], FingerprintSimilarity], Depends(_get_similarity_system_getter)
    ] = _similarity_system_getter,
) -> ComparisonResult:
    """
    Compare two specific tracks for similarity

    Args:
        track_id1: First track ID
        track_id2: Second track ID

    Returns:
        Similarity between the two tracks
    """
    repos = require_repository_factory(get_repository_factory)

    # #4630: shared with /similar and /explain. This route previously
    # validated but never enqueued, so a missing fingerprint here failed
    # permanently while the same track under /similar repaired itself.
    await require_fingerprinted_tracks(repos, track_id1, track_id2)

    # Calculate similarity
    similarity = require_similarity_system(get_similarity_system)

    if not await asyncio.to_thread(similarity.is_fitted):
        raise HTTPException(status_code=503, detail="Similarity system not initialized")

    result = await asyncio.to_thread(similarity.calculate_similarity, track_id1, track_id2)

    if not result:
        raise HTTPException(status_code=500, detail="Failed to calculate similarity")

    return ComparisonResult(
        track_id1=track_id1,
        track_id2=track_id2,
        distance=result.distance,
        similarity_score=result.similarity_score,
    )


@_with_similarity_error_handling("Error explaining similarity")
async def explain_similarity(
    track_id1: int,
    track_id2: int,
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
    repos = require_repository_factory(get_repository_factory)

    # #4630: this route had no repository handle at all, so it performed
    # none of the checks its siblings do — a nonexistent track, a track
    # missing a fingerprint, and a genuine engine failure all surfaced as
    # one opaque "Could not generate explanation", and nothing was ever
    # enqueued, so the explain view failed permanently where /similar
    # would have repaired itself.
    await require_fingerprinted_tracks(repos, track_id1, track_id2)

    similarity = require_similarity_system(get_similarity_system)

    if not await asyncio.to_thread(similarity.is_fitted):
        raise HTTPException(status_code=503, detail="Similarity system not initialized")

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
    repos = require_repository_factory(get_repository_factory)
    similarity = require_similarity_system(get_similarity_system)

    # Check if already fitted
    if await asyncio.to_thread(similarity.is_fitted):
        count = await asyncio.to_thread(repos.fingerprints.get_count)
        return {
            "fitted": True,
            "total_fingerprints": count,
            "message": f"Similarity system already fitted with {count} tracks"
        }

    # Get fingerprint count
    fingerprint_count = await asyncio.to_thread(repos.fingerprints.get_count)

    if fingerprint_count < min_samples:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient fingerprints: {fingerprint_count} < {min_samples}"
        )

    # Fit the similarity system — CPU-bound O(N²); offload to thread
    # so the event loop stays responsive (fixes #2738).
    await asyncio.to_thread(similarity.fit)

    return {
        "fitted": True,
        "total_fingerprints": fingerprint_count,
        "message": f"Successfully fitted similarity system with {fingerprint_count} tracks"
    }


def create_similarity_router(
    get_similarity_system: Callable[[], FingerprintSimilarity],
    get_graph_builder: Callable[[], KNNGraphBuilder | None],
    get_repository_factory: Callable[[], Any]
) -> APIRouter:
    """
    Create similarity API router with dependency injection

    Args:
        get_similarity_system: Callable that returns FingerprintSimilarity instance
        get_graph_builder: Callable that returns KNNGraphBuilder instance
        get_repository_factory: Callable that returns RepositoryFactory instance

    Returns:
        Configured FastAPI router
    """
    global _deps

    deps = _SimilarityDeps(
        get_similarity_system=get_similarity_system,
        get_graph_builder=get_graph_builder,
        get_repository_factory=get_repository_factory,
    )
    _deps = deps

    router = APIRouter(
        prefix="/api/similarity",
        tags=["similarity"],
        dependencies=[Depends(_make_deps_binder(deps))],
    )

    router.add_api_route("/tracks/{track_id}/similar", get_similar_tracks, methods=["GET"], response_model=list[SimilarTrack])
    router.add_api_route("/tracks/{track_id1}/compare/{track_id2}", compare_tracks, methods=["GET"], response_model=ComparisonResult)
    router.add_api_route("/tracks/{track_id1}/explain/{track_id2}", explain_similarity, methods=["GET"], response_model=SimilarityExplanation)
    router.add_api_route("/fit", fit_similarity_system, methods=["POST"], response_model=FitSimilarityResponse)

    return router
