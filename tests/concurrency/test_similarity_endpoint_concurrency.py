# -*- coding: utf-8 -*-

"""
Similarity Endpoint Concurrency Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression coverage for #2752: `similarity.fit` and `find_similar` were moved
to `asyncio.to_thread` so CPU-bound work doesn't block the event loop. No
existing test fired concurrent requests against `/api/similarity/tracks/{id}/
similar` and `/api/similarity/fit`, so a regression that re-introduced sync
blocking (or starved the thread pool under load) would not be caught (#3922).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.similarity import create_similarity_router  # noqa: E402
from auralis.analysis.fingerprint import SimilarityResult  # noqa: E402


def _get_handler(router, path):
    for route in router.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"No route found for path {path!r}")


def _make_router(similarity, repos, graph_builder=None):
    return create_similarity_router(
        get_similarity_system=lambda: similarity,
        get_graph_builder=lambda: graph_builder,
        get_repository_factory=lambda: repos,
    )


def _mock_repos():
    repos = Mock()
    track = Mock()
    track.id = 1
    repos.tracks.get_by_id = Mock(return_value=track)
    repos.tracks.get_by_ids = Mock(return_value={})
    repos.fingerprints.exists = Mock(return_value=True)
    repos.fingerprints.get_count = Mock(return_value=100)
    return repos


class TestConcurrentSimilarTracksRequests:
    """N concurrent GET /tracks/{id}/similar requests against the same graph state."""

    @pytest.mark.asyncio
    async def test_ten_concurrent_requests_all_complete_in_parallel(self):
        """10 concurrent find_similar calls run in parallel, not serialized.

        Each mocked find_similar sleeps inside the real thread pool (via
        asyncio.to_thread). If the endpoint ever reverted to a sync call on
        the event loop, or a shared lock, wall time would approach
        n_requests * call_latency. True concurrency keeps it close to a
        single call's latency.
        """
        call_latency = 0.2
        n_requests = 10

        def slow_find_similar(track_id, n=10):
            time.sleep(call_latency)
            return [SimilarityResult(track_id=track_id + 1, distance=0.1, similarity_score=0.9)]

        similarity = Mock()
        similarity.is_fitted = Mock(return_value=True)
        similarity.find_similar = Mock(side_effect=slow_find_similar)

        router = _make_router(similarity, _mock_repos(), graph_builder=None)
        handler = _get_handler(router, "/api/similarity/tracks/{track_id}/similar")

        start = time.monotonic()
        results = await asyncio.gather(*[
            handler(track_id=1, limit=10, use_graph=False, include_details=False)
            for _ in range(n_requests)
        ])
        elapsed = time.monotonic() - start

        assert len(results) == n_requests
        for result in results:
            assert len(result) == 1
            assert result[0].track_id == 2

        assert similarity.find_similar.call_count == n_requests
        # Generous margin (3x a single call) — still far below the ~2s a
        # serialized implementation would take.
        assert elapsed < call_latency * 3, (
            f"{n_requests} concurrent requests took {elapsed:.2f}s — expected "
            f"close to {call_latency:.2f}s if truly parallel, not "
            f"{call_latency * n_requests:.2f}s (serialized)"
        )

    @pytest.mark.asyncio
    async def test_concurrent_requests_no_deadlock_under_error(self):
        """Concurrent requests where some hit errors don't deadlock the rest.

        Half the calls raise from find_similar; asserts every task resolves
        (success or exception) rather than hanging.
        """
        def flaky_find_similar(track_id, n=10):
            if track_id % 2 == 0:
                raise RuntimeError("simulated similarity backend failure")
            return [SimilarityResult(track_id=track_id + 1, distance=0.1, similarity_score=0.9)]

        similarity = Mock()
        similarity.is_fitted = Mock(return_value=True)
        similarity.find_similar = Mock(side_effect=flaky_find_similar)

        router = _make_router(similarity, _mock_repos(), graph_builder=None)
        handler = _get_handler(router, "/api/similarity/tracks/{track_id}/similar")

        outcomes = await asyncio.wait_for(
            asyncio.gather(*[
                handler(track_id=i, limit=10, use_graph=False, include_details=False)
                for i in range(1, 11)
            ], return_exceptions=True),
            timeout=5.0,
        )

        assert len(outcomes) == 10
        successes = [o for o in outcomes if not isinstance(o, BaseException)]
        failures = [o for o in outcomes if isinstance(o, BaseException)]
        assert len(successes) == 5
        assert len(failures) == 5


class TestFitInterleavedWithRead:
    """POST /fit (long-running write) interleaved with GET .../similar (read)."""

    @pytest.mark.asyncio
    async def test_similar_tracks_completes_while_fit_in_flight(self):
        """A /similar read fired while /fit is in flight completes promptly
        rather than queueing behind the fit's thread-pool slot.

        Regression guard for #2752's asyncio.to_thread offload — a revert to
        a shared lock, or a starved thread pool, would make the read wait
        for the full fit duration instead of running alongside it.
        """
        fit_latency = 0.4
        fit_started = threading.Event()

        def slow_fit():
            fit_started.set()
            time.sleep(fit_latency)

        similarity = Mock()
        similarity.is_fitted = Mock(return_value=False)
        similarity.fit = Mock(side_effect=slow_fit)

        fit_repos = Mock()
        fit_repos.fingerprints.get_count = Mock(return_value=100)

        # The read is served from a pre-computed K-NN graph (the common case
        # while a background re-fit is in progress) so it never touches
        # `similarity.is_fitted`/`find_similar` — this isolates the thing
        # under test (does the read's asyncio.to_thread call share the
        # thread pool without queueing behind the fit's?) from the
        # `is_fitted` business-logic gate, which — correctly — would itself
        # reject a read while the *first* fit is still in flight.
        graph_builder = Mock()
        graph_builder.get_neighbors = Mock(return_value=[
            {"similar_track_id": 2, "distance": 0.1, "similarity_score": 0.9, "rank": 1}
        ])

        fit_router = _make_router(similarity, fit_repos, graph_builder=None)
        read_router = _make_router(similarity, _mock_repos(), graph_builder=graph_builder)

        fit_handler = _get_handler(fit_router, "/api/similarity/fit")
        similar_handler = _get_handler(read_router, "/api/similarity/tracks/{track_id}/similar")

        fit_task = asyncio.create_task(fit_handler(min_samples=10))

        # Deterministically wait until the fit's blocking call has actually
        # started executing in the thread pool (not just been scheduled)
        # before firing the read, without ever blocking the event loop
        # itself (which would starve fit_task of the chance to run at all).
        for _ in range(100):
            if fit_started.is_set():
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("fit did not start within 1s")

        read_start = time.monotonic()
        read_result = await similar_handler(track_id=1, limit=10, use_graph=True, include_details=False)
        read_elapsed = time.monotonic() - read_start

        assert not fit_task.done(), "fit finished before the read fired — not a real interleaving"
        await fit_task

        assert len(read_result) == 1
        assert read_result[0].track_id == 2
        # The read must actually complete promptly, not wait for the fit's
        # full latency — if it were serialized behind the fit's thread-pool
        # slot, read_elapsed would approach fit_latency.
        assert read_elapsed < fit_latency * 0.75, (
            f"/similar read took {read_elapsed:.2f}s while /fit (latency "
            f"{fit_latency:.2f}s) was in flight — looks serialized behind "
            f"the same thread-pool slot"
        )
