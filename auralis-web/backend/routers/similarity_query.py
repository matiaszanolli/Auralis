"""
Similar-track search and pairwise comparison handlers (split from similarity.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from auralis.analysis.fingerprint import FingerprintSimilarity, KNNGraphBuilder, SimilarityResult
from collections.abc import Callable
from fastapi import Depends, HTTPException, Path, Query
from typing import Annotated, Any
import asyncio

from . import dependencies
from .similarity_common import _with_similarity_error_handling, require_fingerprinted_tracks, require_fitted, require_similarity_system
from .similarity_deps import _get_graph_builder_getter, _get_repository_factory_getter, _get_similarity_system_getter, _graph_builder_getter, _repository_factory_getter, _similarity_system_getter
from .similarity_models import ComparisonResult, SimilarTrack


@_with_similarity_error_handling("Error finding similar tracks")
async def get_similar_tracks(
    track_id: Annotated[int, Path(ge=1)],
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
    repos = dependencies.require_repository_factory(get_repository_factory)

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
        similarity = await require_fitted(require_similarity_system(get_similarity_system))

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
    track_id1: Annotated[int, Path(ge=1)],
    track_id2: Annotated[int, Path(ge=1)],
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
    repos = dependencies.require_repository_factory(get_repository_factory)

    # #4630: shared with /similar and /explain. This route previously
    # validated but never enqueued, so a missing fingerprint here failed
    # permanently while the same track under /similar repaired itself.
    await require_fingerprinted_tracks(repos, track_id1, track_id2)

    # Calculate similarity
    similarity = await require_fitted(require_similarity_system(get_similarity_system))

    result = await asyncio.to_thread(similarity.calculate_similarity, track_id1, track_id2)

    if not result:
        raise HTTPException(status_code=500, detail="Failed to calculate similarity")

    return ComparisonResult(
        track_id1=track_id1,
        track_id2=track_id2,
        distance=result.distance,
        similarity_score=result.similarity_score,
    )
