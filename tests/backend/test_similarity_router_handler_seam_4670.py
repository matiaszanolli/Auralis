"""
Regression tests for the similarity router's closure-to-module-level
extraction (#4670).

create_similarity_router() used to be one 260-line closure -- every handler
was a nested `async def` reachable only by constructing the whole router with
its full dependency graph. Handlers are now module-level `async def`
functions whose dependency parameters carry a FastAPI Depends() annotation
*and* a plain default, so a caller that wants to unit-test one directly just
passes its own getter as a keyword argument, bypassing Depends() (and
_SimilarityDeps, and the router) entirely. These tests exist to prove that
seam is real, not just that it types.

Note what is injected: the *getter*, not the resolved object. `/similar`
only needs a similarity system on its real-time fallback path, and
`/compare` resolves one only after its 404 preconditions pass -- so these
stay lazy, and the stubs below are `lambda: <mock>`.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.similarity import (  # noqa: E402
    ComparisonResult,
    SimilarTrack,
    compare_tracks,
    fit_similarity_system,
    get_similar_tracks,
)

pytestmark = pytest.mark.asyncio


def _repos(track_ids=(1, 2), fingerprinted=(1, 2)) -> Mock:
    """A repository factory where exactly `track_ids` exist."""
    repos = Mock()
    repos.tracks.get_by_id = Mock(side_effect=lambda tid: Mock(id=tid) if tid in track_ids else None)
    repos.tracks.get_by_ids = Mock(return_value={})
    repos.fingerprints.exists = Mock(side_effect=lambda tid: tid in fingerprinted)
    repos.fingerprints.get_count = Mock(return_value=100)
    return repos


async def test_get_similar_tracks_callable_with_bare_stub_getters():
    """No router, no _SimilarityDeps, no app -- just the handler and stubs."""
    repos = _repos()
    graph_builder = MagicMock()
    graph_builder.get_neighbors.return_value = [
        {"similar_track_id": 7, "distance": 0.1, "similarity_score": 0.9, "rank": 1}
    ]

    results = await get_similar_tracks(
        track_id=1,
        limit=1,
        use_graph=True,
        include_details=False,
        get_repository_factory=lambda: repos,
        get_graph_builder=lambda: graph_builder,
        get_similarity_system=lambda: MagicMock(),
    )

    assert [r.track_id for r in results] == [7]
    assert isinstance(results[0], SimilarTrack)


async def test_get_similar_tracks_falls_back_to_the_real_time_search():
    """use_graph=False skips the graph getter entirely and asks the system."""
    repos = _repos()
    similarity = MagicMock()
    similarity.is_fitted.return_value = True
    similarity.find_similar.return_value = [
        Mock(track_id=42, distance=0.2, similarity_score=0.8)
    ]
    graph_builder = MagicMock()

    results = await get_similar_tracks(
        track_id=1,
        limit=1,
        use_graph=False,
        include_details=False,
        get_repository_factory=lambda: repos,
        get_graph_builder=lambda: graph_builder,
        get_similarity_system=lambda: similarity,
    )

    assert [r.track_id for r in results] == [42]
    graph_builder.get_neighbors.assert_not_called()


async def test_compare_tracks_callable_with_bare_stub_getters():
    similarity = MagicMock()
    similarity.is_fitted.return_value = True
    similarity.calculate_similarity.return_value = Mock(distance=0.25, similarity_score=0.75)

    result = await compare_tracks(
        track_id1=1,
        track_id2=2,
        get_repository_factory=lambda: _repos(),
        get_similarity_system=lambda: similarity,
    )

    assert isinstance(result, ComparisonResult)
    assert (result.track_id1, result.track_id2) == (1, 2)
    assert result.similarity_score == 0.75


async def test_compare_tracks_404_precondition_survives_the_direct_call():
    """The shared #4630 precondition still runs when Depends() is bypassed."""
    from routers.errors import NotFoundError

    with patch(
        "routers.similarity_common.enqueue_for_fingerprinting", new_callable=AsyncMock
    ):
        with pytest.raises(NotFoundError):
            await compare_tracks(
                track_id1=999,
                track_id2=2,
                get_repository_factory=lambda: _repos(),
                get_similarity_system=lambda: MagicMock(),
            )


async def test_fit_similarity_system_callable_with_bare_stub_getters():
    similarity = MagicMock()
    similarity.is_fitted.return_value = False

    result = await fit_similarity_system(
        min_samples=10,
        get_repository_factory=lambda: _repos(),
        get_similarity_system=lambda: similarity,
    )

    assert result["fitted"] is True
    assert result["total_fingerprints"] == 100
    similarity.fit.assert_called_once()
