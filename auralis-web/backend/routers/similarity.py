"""
Similarity API Router
~~~~~~~~~~~~~~~~~~~~

REST API endpoints for fingerprint-based music similarity

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, Depends


from auralis.analysis.fingerprint import (
    FingerprintSimilarity,
    KNNGraphBuilder,
)


# Shared error helpers live in similarity_common (#4270) so the similarity-graph
# and fingerprint-queue routers can reuse them. Re-exported here for backward
# compatibility (e.g. tests importing routers.similarity._internal_error_response).
from .similarity_common import (  # noqa: F401
    _internal_error_response,
    _with_similarity_error_handling,
    require_fingerprinted_tracks,
    require_fitted,
    require_similarity_system,
)
from .similarity_models import (  # noqa: F401
    ComparisonResult,
    DimensionContribution,
    EXPLAINABLE_DIMENSIONS,
    FitSimilarityResponse,
    SimilarTrack,
    SimilarityExplanation,
)
from .similarity_deps import (  # noqa: F401
    _SimilarityDeps,
    _deps,
    _get_graph_builder_getter,
    _get_repository_factory_getter,
    _get_similarity_system_getter,
    _graph_builder_getter,
    _repository_factory_getter,
    _similarity_system_getter,
    _unavailable,
)
from .similarity_query import (  # noqa: F401
    compare_tracks,
    get_similar_tracks,
)
from .similarity_explain import (  # noqa: F401
    explain_similarity,
    fit_similarity_system,
)


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
    deps = _SimilarityDeps(
        get_similarity_system=get_similarity_system,
        get_graph_builder=get_graph_builder,
        get_repository_factory=get_repository_factory,
    )

    router = APIRouter(
        prefix="/api/similarity",
        tags=["similarity"],
        dependencies=[Depends(_deps.bind(deps))],
    )

    router.add_api_route("/tracks/{track_id}/similar", get_similar_tracks, methods=["GET"], response_model=list[SimilarTrack])
    router.add_api_route("/tracks/{track_id1}/compare/{track_id2}", compare_tracks, methods=["GET"], response_model=ComparisonResult)
    router.add_api_route("/tracks/{track_id1}/explain/{track_id2}", explain_similarity, methods=["GET"], response_model=SimilarityExplanation)
    router.add_api_route("/fit", fit_similarity_system, methods=["POST"], response_model=FitSimilarityResponse)

    return router
