"""
Explain-similarity preconditions and their unification with the siblings (#4630)

``/compare`` validated both track ids and both fingerprints, raising precise
404s. ``/explain`` — the same conceptual operation on the same two ids, one route
down — had no repository handle at all, so it performed none of those checks and
folded every possible cause (nonexistent track, missing fingerprint on either
side, engine failure) into a single ``"Could not generate explanation"``. Unlike
``/similar`` it also never enqueued a missing fingerprint, so the explain path
could never self-heal: the same track that repaired itself under "Similar
Tracks" failed permanently under the explanation view.

The three routes had three different policies. They now share
``similarity_common.require_fingerprinted_tracks``, so:
  * a nonexistent track yields a 404 naming that track;
  * a track missing a fingerprint yields a distinct 404 naming that track, and
    is enqueued for background processing — on all three routes, not just
    ``/similar``;
  * ``/explain``'s remaining falsy-return 404 now means specifically "the engine
    could not explain this pair", which is the only cause left.

``top_n``'s upper bound is derived from the dimension list the explanation
actually slices rather than the literal 25.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import inspect
import sys
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from routers import similarity as similarity_module  # noqa: E402
from routers.similarity import EXPLAINABLE_DIMENSIONS  # noqa: E402
from routers.similarity_common import require_fingerprinted_tracks  # noqa: E402

from auralis.analysis.fingerprint import FingerprintNormalizer  # noqa: E402

EXPLAIN = "/api/similarity/tracks/{a}/explain/{b}"
COMPARE = "/api/similarity/tracks/{a}/compare/{b}"
SIMILAR = "/api/similarity/tracks/{a}/similar"


@pytest.fixture(autouse=True)
def _no_rate_limiting():
    """Take RateLimitMiddleware out of the picture for this module.

    `/api/similarity` is capped at 20 requests per 60 s, and the middleware
    instance is built once with the app — which `sys.modules` caches for the
    whole pytest process. So the budget is consumed *across* test files: this
    module passes in isolation but every request 429s when it runs after
    test_similarity_api.py, which alone exceeds 20 similarity requests.

    Clearing `_RATE_LIMITS` makes the prefix match miss and the middleware pass
    through, so these tests assert on router behaviour rather than on whichever
    file happened to run first. This is a pre-existing, wider isolation hazard
    (it accounts for failures in test_similarity_api.py itself) — not something
    #4630 introduced, and not fixed here.
    """
    from config.middleware import RateLimitMiddleware

    with patch.object(RateLimitMiddleware, "_RATE_LIMITS", {}):
        yield


@pytest.fixture
def repos():
    """A repository factory where nothing exists until a test says otherwise."""
    factory = Mock()
    factory.tracks = Mock()
    factory.fingerprints = Mock()
    factory.tracks.get_by_id = Mock(return_value=None)
    factory.fingerprints.exists = Mock(return_value=False)
    return factory


@pytest.fixture
def queue():
    """Intercept the lazily-imported fingerprint queue and record enqueues."""
    q = Mock()
    q.enqueue = Mock(return_value=True)
    with patch("analysis.fingerprint_queue.get_fingerprint_queue", return_value=q):
        yield q


def _tracks_exist(repos, *ids: int) -> None:
    """Make exactly `ids` resolvable, everything else missing."""
    known = set(ids)
    repos.tracks.get_by_id.side_effect = (
        lambda tid: Mock(id=tid) if tid in known else None
    )


def _fingerprints_exist(repos, *ids: int) -> None:
    known = set(ids)
    repos.fingerprints.exists.side_effect = lambda tid: tid in known


class TestExplainNamesTheMissingTrack:
    """Acceptance: a 404 that says *which* track is missing."""

    @patch("routers.similarity.require_repository_factory")
    def test_nonexistent_first_track_is_named(self, require_repos, client, repos, queue):
        require_repos.return_value = repos
        _tracks_exist(repos, 2)

        response = client.get(EXPLAIN.format(a=999, b=2))

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "999" in detail, (
            f"404 does not name the missing track: {detail!r} — pre-fix this was "
            "the generic 'Could not generate explanation' (#4630)"
        )

    @patch("routers.similarity.require_repository_factory")
    def test_nonexistent_second_track_is_named(self, require_repos, client, repos, queue):
        require_repos.return_value = repos
        _tracks_exist(repos, 1)

        response = client.get(EXPLAIN.format(a=1, b=998))

        assert response.status_code == 404
        assert "998" in response.json()["detail"]

    @patch("routers.similarity.require_repository_factory")
    def test_missing_track_is_not_reported_as_missing_fingerprint(
        self, require_repos, client, repos, queue
    ):
        """The two causes must stay distinguishable, and not be conflated.

        A nonexistent track trivially has no fingerprint; reporting the weaker
        cause would send the caller waiting for a queue entry that will never be
        created.
        """
        require_repos.return_value = repos
        _tracks_exist(repos, 2)

        detail = client.get(EXPLAIN.format(a=999, b=2)).json()["detail"]

        assert "fingerprint" not in detail.lower(), (
            f"nonexistent track reported as a fingerprint problem: {detail!r}"
        )
        queue.enqueue.assert_not_called()


class TestExplainEnqueuesMissingFingerprints:
    """Acceptance: the explain path self-heals, matching /similar."""

    @patch("routers.similarity.require_repository_factory")
    def test_missing_fingerprint_yields_a_distinct_404(
        self, require_repos, client, repos, queue
    ):
        require_repos.return_value = repos
        _tracks_exist(repos, 1, 2)
        _fingerprints_exist(repos, 2)  # track 1 has none

        response = client.get(EXPLAIN.format(a=1, b=2))

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "1" in detail and "fingerprint" in detail.lower(), (
            f"missing-fingerprint 404 does not identify the cause: {detail!r}"
        )

    @patch("routers.similarity.require_repository_factory")
    def test_missing_fingerprint_is_enqueued(self, require_repos, client, repos, queue):
        require_repos.return_value = repos
        _tracks_exist(repos, 1, 2)
        _fingerprints_exist(repos, 2)

        client.get(EXPLAIN.format(a=1, b=2))

        assert queue.enqueue.call_args_list == [call(1)], (
            "explain did not enqueue the un-fingerprinted track, so the failure "
            "is permanent — the same track under /similar repairs itself (#4630)"
        )

    @patch("routers.similarity.require_repository_factory")
    def test_second_track_missing_fingerprint_is_enqueued(
        self, require_repos, client, repos, queue
    ):
        require_repos.return_value = repos
        _tracks_exist(repos, 1, 2)
        _fingerprints_exist(repos, 1)

        client.get(EXPLAIN.format(a=1, b=2))

        queue.enqueue.assert_called_once_with(2)

    @patch("routers.similarity.require_repository_factory")
    def test_an_unavailable_queue_does_not_turn_the_404_into_a_500(
        self, require_repos, client, repos
    ):
        """Enqueueing is best-effort; it must never change the response."""
        require_repos.return_value = repos
        _tracks_exist(repos, 1, 2)
        _fingerprints_exist(repos, 2)

        with patch(
            "analysis.fingerprint_queue.get_fingerprint_queue",
            side_effect=RuntimeError("queue not constructed"),
        ):
            response = client.get(EXPLAIN.format(a=1, b=2))

        assert response.status_code == 404


class TestSiblingRoutesShareOnePolicy:
    """CONSISTENCY: one helper, not three open-coded policies."""

    @patch("routers.similarity.require_repository_factory")
    def test_compare_also_enqueues_a_missing_fingerprint(
        self, require_repos, client, repos, queue
    ):
        """/compare validated but never enqueued — now it does, like /similar."""
        require_repos.return_value = repos
        _tracks_exist(repos, 1, 2)
        _fingerprints_exist(repos, 2)

        response = client.get(COMPARE.format(a=1, b=2))

        assert response.status_code == 404
        queue.enqueue.assert_called_once_with(1)

    @patch("routers.similarity.require_repository_factory")
    def test_similar_still_enqueues(self, require_repos, client, repos, queue):
        """The one route that already self-healed must not have regressed."""
        require_repos.return_value = repos
        _tracks_exist(repos, 1)
        _fingerprints_exist(repos)  # none

        response = client.get(SIMILAR.format(a=1))

        assert response.status_code == 404
        queue.enqueue.assert_called_once_with(1)

    @patch("routers.similarity.require_repository_factory")
    def test_similar_still_404s_on_a_nonexistent_track(
        self, require_repos, client, repos, queue
    ):
        require_repos.return_value = repos
        _tracks_exist(repos)  # nothing exists

        assert client.get(SIMILAR.format(a=999)).status_code == 404

    def test_all_three_routes_use_the_shared_helper(self):
        """A copy left behind would recreate the divergence this issue is about."""
        # Module source, not create_similarity_router's: #4670 hoisted the
        # handlers out of the factory closure to module level, so the factory
        # is now only the ~20-line assembler that registers them.
        source = inspect.getsource(similarity_module)

        assert source.count("require_fingerprinted_tracks(") == 3, (
            "expected /similar, /compare and /explain to each call the shared "
            "precondition helper exactly once (#4630)"
        )
        # And no route may still hand-roll the fingerprint check.
        assert "repos.fingerprints.exists" not in source, (
            "a route still open-codes the fingerprint precondition instead of "
            "using require_fingerprinted_tracks (#4630)"
        )

    @pytest.mark.parametrize(
        "path,method",
        [
            ("/api/similarity/tracks/{track_id1}/explain/{track_id2}", "GET"),
            ("/api/similarity/tracks/{track_id1}/compare/{track_id2}", "GET"),
            ("/api/similarity/tracks/{track_id}/similar", "GET"),
        ],
    )
    def test_each_track_route_acquires_a_repository_factory(self, path, method):
        """WIRING: without a repository handle the helper cannot be called at all.

        Counting occurrences across the whole factory function is not enough —
        ``/fit`` also acquires one, so a bare count of three still passes while
        ``explain_similarity`` has none. Inspect each endpoint's own body.
        """
        router = similarity_module.create_similarity_router(
            get_similarity_system=lambda: Mock(),
            get_graph_builder=lambda: None,
            get_repository_factory=lambda: Mock(),
        )
        route = next(
            r for r in router.routes
            if getattr(r, "path", "") == path and method in getattr(r, "methods", set())
        )
        body = inspect.getsource(route.endpoint)

        assert "require_repository_factory(get_repository_factory)" in body, (
            f"{route.endpoint.__name__} has no repository handle, so its "
            "preconditions cannot run and the fix would be inert (#4630)"
        )
        assert "require_fingerprinted_tracks(" in body, (
            f"{route.endpoint.__name__} does not enforce the shared preconditions"
        )


class TestExplainRemainingFailureIsNarrowed:
    """RETURN VALUE: a falsy engine return now has exactly one meaning."""

    @patch("routers.similarity.require_repository_factory")
    def test_engine_failure_message_blames_the_engine(
        self, require_repos, client, repos, queue
    ):
        require_repos.return_value = repos
        _tracks_exist(repos, 1, 2)
        _fingerprints_exist(repos, 1, 2)  # both valid — preconditions all pass

        system = Mock()
        system.is_fitted = Mock(return_value=True)
        system.get_similarity_explanation = Mock(return_value=None)

        with patch("routers.similarity.require_similarity_system", return_value=system):
            response = client.get(EXPLAIN.format(a=1, b=2))

        assert response.status_code == 404
        detail = response.json()["detail"].lower()
        assert "engine" in detail or "could not explain" in detail, (
            f"the narrowed failure is still described generically: {detail!r}"
        )
        assert "1" in response.json()["detail"] and "2" in response.json()["detail"]


class TestTopNBoundIsDerived:
    """Acceptance: the bound tracks the vector definition, not a literal."""

    def test_bound_equals_the_dimension_list_the_explanation_slices(self):
        """`get_dimension_contributions` enumerates these names, so it is the
        list `top_n` truncates — the authoritative source for the bound."""
        assert EXPLAINABLE_DIMENSIONS == len(FingerprintNormalizer.DIMENSION_NAMES)

    def test_bound_is_not_a_hard_coded_literal_in_the_route(self):
        # The route that declares `top_n`, rather than the factory that
        # registers it — the handler moved to module level in #4670.
        source = inspect.getsource(similarity_module.explain_similarity)
        assert "le=EXPLAINABLE_DIMENSIONS" in source, (
            "top_n's upper bound is not derived from the dimension count (#4630)"
        )
        assert "le=25" not in source, "top_n still hard-codes today's count"

    @patch("routers.similarity.require_repository_factory")
    def test_top_n_at_the_bound_is_accepted(self, require_repos, client, repos, queue):
        """Accepted by validation — the 404 below is the precondition, not 422."""
        require_repos.return_value = repos
        _tracks_exist(repos)

        response = client.get(
            EXPLAIN.format(a=1, b=2), params={"top_n": EXPLAINABLE_DIMENSIONS}
        )

        assert response.status_code != 422, (
            f"top_n={EXPLAINABLE_DIMENSIONS} rejected despite that many "
            "dimensions existing"
        )

    @patch("routers.similarity.require_repository_factory")
    def test_top_n_above_the_bound_is_rejected(self, require_repos, client, repos, queue):
        require_repos.return_value = repos
        _tracks_exist(repos)

        response = client.get(
            EXPLAIN.format(a=1, b=2), params={"top_n": EXPLAINABLE_DIMENSIONS + 1}
        )

        assert response.status_code == 422


class TestHelperUnit:
    """Direct unit coverage of the extracted precondition."""

    @pytest.mark.asyncio
    async def test_checks_existence_for_every_id_before_any_fingerprint(self, repos, queue):
        """Ordering is the property that keeps the two causes distinguishable."""
        _tracks_exist(repos, 1)  # id 2 does not exist
        _fingerprints_exist(repos)  # neither has a fingerprint

        from routers.errors import NotFoundError

        with pytest.raises(NotFoundError) as excinfo:
            await require_fingerprinted_tracks(repos, 1, 2)

        # Must report the nonexistent id 2, not id 1's missing fingerprint.
        assert "2" in str(excinfo.value.detail)
        assert "fingerprint" not in str(excinfo.value.detail).lower()

    @pytest.mark.asyncio
    async def test_passes_silently_when_everything_is_present(self, repos, queue):
        _tracks_exist(repos, 1, 2)
        _fingerprints_exist(repos, 1, 2)

        assert await require_fingerprinted_tracks(repos, 1, 2) is None
        queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_accepts_a_single_id(self, repos, queue):
        """/similar passes one id; /compare and /explain pass two."""
        _tracks_exist(repos, 1)
        _fingerprints_exist(repos, 1)

        assert await require_fingerprinted_tracks(repos, 1) is None
