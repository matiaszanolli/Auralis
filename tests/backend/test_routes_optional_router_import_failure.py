"""
Regression tests for setup_routers() import-time robustness (#3907).

cache_streamlined and similarity each wrap their
app.include_router(...) call in try/except so a broken transitive
dependency degrades gracefully instead of crashing startup (fixes #2324).
That protection was previously bypassed because their factory functions
were imported at module load time (top of config/routes.py), outside any
try/except — a broken import raised before the protected block was ever
reached. The fix moves those imports inside their own try/except,
matching the pattern already used for processing_api, so the import is
deferred to when setup_routers() actually runs.

Note: this deliberately does NOT force-reload config.routes itself (e.g.
via sys.modules.pop + importlib.reload) to reproduce the pre-fix crash —
doing so mutates global import-cache state for config.routes/config that
bleeds into other test modules sharing the session (confirmed via a
git-worktree A/B run: it broke ~65 unrelated tests when this file ran
before test_main_api.py). The historical pre-fix-vs-post-fix behavior was
instead verified manually via git worktree during development. What's
shipped here still catches the regression that matters going forward: a
broken transitive import for one of these three routers, discovered at
the point setup_routers() actually imports it.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


def _flattened_routes(app):
    """Every registered route, unwrapping FastAPI's lazy `_IncludedRouter`.

    Newer FastAPI (0.141+) wraps each `app.include_router(...)` call in a
    `_IncludedRouter` placeholder on `app.routes` instead of the plain
    `APIRoute` objects older versions exposed directly — `route.path` raises
    AttributeError on it. The real routes live at
    `_IncludedRouter.original_router.routes`. Older FastAPI (no such
    wrapper) falls through the `getattr(..., None)` unchanged, so this stays
    correct either way.
    """
    routes = []
    for route in app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            routes.extend(original_router.routes)
        else:
            routes.append(route)
    return routes


def _paths(app) -> set[str]:
    return {r.path for r in _flattened_routes(app) if hasattr(r, "path")}


def _path_method_pairs(app) -> list[tuple[str, str]]:
    """(path, method) for every operation, WITHOUT deduplication.

    Deliberately not `app.openapi()['paths']`: two routers registering the
    same (path, method) collapse to a single OpenAPI operation — picking the
    LAST-registered router's schema — while Starlette's actual routing picks
    the FIRST match at request time. The two disagree on which handler is
    "real", which is exactly the shadowing hazard #4717 exists to catch, so
    only the raw, duplicate-preserving route list can detect it.
    """
    pairs = []
    for r in _flattened_routes(app):
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None)
        if not path or not methods:
            continue
        pairs.extend((path, m) for m in methods)
    return pairs


def _base_deps() -> dict:
    return {
        'HAS_PROCESSING': False,
        'HAS_STREAMLINED_CACHE': True,
        'HAS_SIMILARITY': True,
        'HAS_AURALIS': False,
        'manager': None,
        'enhancement_settings': {},
        'chunked_audio_processor_class': None,
        'create_track_info_fn': None,
        'buffer_presets_fn': None,
        'globals': {},
    }


@pytest.mark.parametrize(
    "broken_module",
    ["routers.cache_streamlined", "routers.similarity"],
)
def test_broken_optional_router_import_does_not_crash_setup(broken_module):
    """A broken import for an optional router must not prevent the other
    routers from being registered (#3907)."""
    from fastapi import FastAPI

    from config.routes import setup_routers

    app = FastAPI()

    # Setting a module to None in sys.modules makes any subsequent
    # `import <module>` (including `from <module> import X`) raise
    # ImportError. setup_routers()'s local imports for these three routers
    # run at call time, so patching right before the call exercises the
    # same failure path a genuinely broken transitive dependency would.
    with patch.dict(sys.modules, {broken_module: None}):
        setup_routers(app, _base_deps())  # must not raise

    # Core, unconditionally-required routers must still be registered.
    paths = _paths(app)
    assert any(p == "/api/albums" for p in paths)
    assert any(p == "/api/library/tracks" for p in paths)


def test_all_routers_register_when_nothing_is_broken():
    """Sanity check: with no broken imports, cache/similarity/wav-streaming
    routes are actually present (guards against the parametrized test above
    passing vacuously because the routes were never registered anyway)."""
    from fastapi import FastAPI

    from config.routes import setup_routers

    app = FastAPI()
    setup_routers(app, _base_deps())

    paths = _paths(app)
    assert any(p.startswith("/api/similarity") for p in paths)
    assert any(p == "/api/albums" for p in paths)


# ============================================================================
# #4717: the composed-app surface for the #4270 three-router similarity split.
#
# similarity/similarity_graph/fingerprint_queue all mount under the shared
# /api/similarity prefix inside ONE try/except (config/routes.py). Per-router
# unit tests (test_similarity_api.py) mount each router individually into its
# own throwaway FastAPI() app, so they verify each router in isolation but
# never the composed application — nothing asserted the three route tables
# were disjoint, nor that one router's broken import doesn't silently drop
# the other two's endpoints as well. These tests exercise the real
# setup_routers() composition, which is the only place that blind spot
# could be caught.
# ============================================================================

EXPECTED_SIMILARITY_PATHS = {
    "/api/similarity/tracks/{track_id}/similar",
    "/api/similarity/tracks/{track_id1}/compare/{track_id2}",
    "/api/similarity/tracks/{track_id1}/explain/{track_id2}",
    "/api/similarity/fit",
    "/api/similarity/graph/build",
    "/api/similarity/graph/stats",
    "/api/similarity/graph",
    "/api/similarity/fingerprint-queue/status",
    "/api/similarity/fingerprint-queue/enqueue/{track_id}",
    "/api/similarity/fingerprint-queue/enqueue-all",
    "/api/similarity/fingerprint-stats",
}


class TestSimilarityRouterFamilyComposition:
    def test_composed_app_exposes_the_expected_similarity_paths(self):
        from fastapi import FastAPI

        from config.routes import setup_routers

        app = FastAPI()
        setup_routers(app, _base_deps())

        similarity_paths = {p for p in _paths(app) if p.startswith("/api/similarity")}
        assert similarity_paths == EXPECTED_SIMILARITY_PATHS

    def test_no_path_method_pair_is_registered_twice(self):
        """Guards against a future path added to one of the three routers
        shadowing another (e.g. a `/graph/{name}` catching `/graph/stats`) —
        that would pass every existing per-router test and only fail at
        runtime, since Starlette silently routes to whichever match came
        first."""
        from fastapi import FastAPI

        from config.routes import setup_routers

        app = FastAPI()
        setup_routers(app, _base_deps())

        pairs = _path_method_pairs(app)
        similarity_pairs = [p for p in pairs if p[0].startswith("/api/similarity")]

        assert len(similarity_pairs) == len(set(similarity_pairs)), (
            f"duplicate (path, method) registered under /api/similarity: "
            f"{[p for p in similarity_pairs if similarity_pairs.count(p) > 1]}"
        )

    def test_a_broken_import_silently_drops_all_three_routers(self):
        """Pins the sharper half of #4717: similarity/similarity_graph/
        fingerprint_queue share ONE try/except, so a broken transitive
        import in any single one of them takes down all three — not just
        the broken one. This is the all-or-nothing failure mode the issue
        asks to make detectable; splitting the try/except three ways is a
        deliberate follow-up, not done here (see #4717's Proposed Fix)."""
        from fastapi import FastAPI

        from config.routes import setup_routers

        app = FastAPI()
        with patch.dict(sys.modules, {"routers.similarity_graph": None}):
            setup_routers(app, _base_deps())  # must not raise (#3907)

        similarity_paths = {p for p in _paths(app) if p.startswith("/api/similarity")}
        assert similarity_paths == set(), (
            "expected the shared try/except to drop ALL THREE similarity "
            "routers when just one (similarity_graph) fails to import — "
            f"got {similarity_paths!r}. If this now fails because the "
            "try/except was split per-router (#4717 follow-up), update this "
            "test to assert only similarity_graph's paths are missing."
        )
