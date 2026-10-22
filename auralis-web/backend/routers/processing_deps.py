"""
Processing Router Dependency Wiring

The Depends() providers every /api/processing handler resolves the engine and
enhancement settings through (#4670), shared by routers/processing_api.py,
processing_jobs.py and processing_parameters.py (#5472).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from core.processing_engine import ProcessingEngine

from .dependencies import RouterDeps

# ============================================================================
# DEPENDENCY WIRING (#4670)
#
# create_processing_router() used to be a 570-line closure: every
# /api/processing handler was nested inside it purely to reach get_processing_engine /
# get_enhancement_settings through closure capture, which made a handler
# impossible to import or call without first building the whole router.
# Handlers are now module level; they reach the same callables through
# FastAPI Depends() instead.
#
# _ProcessingDeps holds the raw callables the factory receives. `_deps` is the
# module-level holder, populated by create_processing_router() itself -- in
# production that happens exactly once per process (config/routes.py calls the
# factory a single time at startup).
#
# Unlike the player router (#4670's first slice), this factory *is* called
# more than once per process: tests/backend/test_processing_api.py builds a
# fresh router per test around a mock engine while main.app's own router --
# built at import time with the real engine getter *and* the enhancement
# settings getter -- is still live in the same process. A single module-level
# holder would be last-writer-wins across those routers, so a later test
# driving main.app (e.g. tests/backend/test_processing_parameters.py) would
# silently get the mock engine and a None enhancement-settings getter.
# Each factory call therefore also builds its own _ProcessingDeps and binds it
# through RouterDeps (dependencies.py): a router-level dependency publishes it
# for the duration of a request, so every provider below resolves against the
# deps of the router that matched. `_deps` falls back to the most recently
# bound deps for anything resolved outside a request.
#
# A handler's Depends() default is only consulted when FastAPI itself invokes
# it for a real request; a direct unit-test call passes the dependency
# explicitly as a keyword argument and never touches _ProcessingDeps or the
# ContextVar at all -- that is the seam #4670 asked for.
# ============================================================================


class _ProcessingDeps:
    """Raw dependencies one create_processing_router() call was handed."""

    def __init__(
        self,
        get_processing_engine: Callable[[], ProcessingEngine | None] | None = None,
        get_enhancement_settings: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.get_processing_engine: Callable[[], ProcessingEngine | None] = (
            get_processing_engine if get_processing_engine is not None else (lambda: None)
        )
        self.get_enhancement_settings = get_enhancement_settings


_deps = RouterDeps("processing", _ProcessingDeps())


def _get_processing_engine() -> ProcessingEngine | None:
    """Live ProcessingEngine, or None when it has not been initialised."""
    return _deps.current().get_processing_engine()


def _get_enhancement_settings() -> Callable[[], dict[str, Any]] | None:
    """The enhancement-settings *getter*, or None when the factory omitted it.

    Returns the callable rather than the settings dict so GET /parameters can
    still tell "not wired up" (503) from "wired up and empty" (#5073), exactly
    as it did when it read the closure variable directly.
    """
    return _deps.current().get_enhancement_settings
