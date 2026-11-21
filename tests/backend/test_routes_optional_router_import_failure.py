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


def test_processing_parameters_is_gated_with_its_processing_api_siblings():
    """#5073: GET /api/processing/parameters moved from the always-registered
    enhancement router onto processing_api's HAS_PROCESSING-gated router, so
    it now shares fate with the other 8 /api/processing/* routes instead of
    being present when they're absent."""
    from fastapi import FastAPI

    from config.routes import setup_routers

    deps = _base_deps()
    deps['HAS_PROCESSING'] = False

    app = FastAPI()
    setup_routers(app, deps)

    pairs = _path_method_pairs(app)
    # None of the /api/processing/* routes should be registered, including
    # the one that used to be unconditional.
    assert not any(p.startswith("/api/processing") for p, _m in pairs)


def test_processing_parameters_is_registered_when_processing_api_is_available():
    """Sanity check for the test above: with HAS_PROCESSING=True, /api/processing/parameters
    is actually present (guards against the gating test passing vacuously)."""
    from fastapi import FastAPI

    from config.routes import setup_routers

    deps = _base_deps()
    deps['HAS_PROCESSING'] = True

    app = FastAPI()
    setup_routers(app, deps)

    pairs = _path_method_pairs(app)
    assert ('/api/processing/parameters', 'GET') in pairs
    # Confirm it's on processing_api's router, not still duplicated onto
    # enhancement — exactly one GET registration for this path.
    assert sum(1 for p, m in pairs if p == '/api/processing/parameters' and m == 'GET') == 1


# ============================================================================
# #4717: the composed-app surface for the #4270 three-router similarity split.
#
# similarity/similarity_graph/fingerprint_queue all mount under the shared
# /api/similarity prefix, each in its own try/except since #6601 (config/routes.py). Per-router
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

    @pytest.mark.parametrize(
        ("broken_module", "lost_prefixes"),
        [
            ("routers.similarity", ("/api/similarity/tracks", "/api/similarity/fit")),
            ("routers.similarity_graph", ("/api/similarity/graph",)),
            ("routers.fingerprint_queue", ("/api/similarity/fingerprint-queue",)),
        ],
    )
    def test_a_broken_import_drops_only_its_own_router(self, broken_module, lost_prefixes):
        """Each of the three routers registers in its own try/except (#6601): a
        broken transitive import in one used to take down all three (the
        all-or-nothing mode #4717 made detectable), and now drops only its own
        endpoints."""
        from fastapi import FastAPI

        from config.routes import setup_routers

        app = FastAPI()
        with patch.dict(sys.modules, {broken_module: None}):
            setup_routers(app, _base_deps())  # must not raise (#3907)

        similarity_paths = {p for p in _paths(app) if p.startswith("/api/similarity")}
        expected = {p for p in EXPECTED_SIMILARITY_PATHS if not p.startswith(lost_prefixes)}
        assert expected and expected != EXPECTED_SIMILARITY_PATHS  # the split is not vacuous
        assert similarity_paths == expected
