"""
Regression tests for setup_routers() import-time robustness (#3907).

cache_streamlined, similarity, and wav_streaming each wrap their
app.include_router(...) call in try/except so a broken transitive
dependency degrades gracefully instead of crashing startup (fixes #2324).
That protection was previously bypassed because their factory functions
were imported at module load time (top of config/routes.py), outside any
try/except — a broken import raised before the protected block was ever
reached. The fix moves those three imports inside their own try/except,
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
    ["routers.cache_streamlined", "routers.similarity", "routers.wav_streaming"],
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
    paths = {route.path for route in app.routes}
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

    paths = {route.path for route in app.routes}
    assert any(p.startswith("/api/similarity") for p in paths)
    assert any(p == "/api/albums" for p in paths)
