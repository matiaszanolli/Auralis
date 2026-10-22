"""
Pin each converted router's registered ``(path, methods)`` set (#5832).

#5832 turned eight more ``create_*_router()`` closures into module-level
handlers assembled with ``add_api_route``. A dropped or mistyped registration
would otherwise be silent -- the module imports fine and the route just 404s.
The expected sets below were captured from the decorator-based routers *before*
the conversion. The settings and system routers pin theirs in
``test_settings_router_handler_seam_5832.py`` /
``test_system_router_handler_seam_5832.py``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.artists import create_artists_router  # noqa: E402
from routers.cache_streamlined import create_streamlined_cache_router  # noqa: E402
from routers.fingerprint_queue import create_fingerprint_queue_router  # noqa: E402
from routers.health import create_health_router  # noqa: E402
from routers.fingerprint_status import create_fingerprint_status_router  # noqa: E402
from routers.library import create_library_router  # noqa: E402
from routers.similarity_graph import create_similarity_graph_router  # noqa: E402
from routers.tracks import create_tracks_router  # noqa: E402


def _none() -> Any:
    return None


_CASES: list[tuple[str, Callable[[], Any], set[tuple[str, tuple[str, ...]]]]] = [
    ("tracks", lambda: create_tracks_router(_none), {
        ("/api/library/tracks", ("GET",)),
        ("/api/library/tracks/favorites", ("GET",)),
        ("/api/library/tracks/{track_id}", ("GET",)),
        ("/api/library/tracks/{track_id}/favorite", ("DELETE",)),
        ("/api/library/tracks/{track_id}/favorite", ("POST",)),
        ("/api/library/tracks/{track_id}/lyrics", ("GET",)),
    }),
    ("artists", lambda: create_artists_router(_none), {
        ("/api/artists", ("GET",)),
        ("/api/artists/{artist_id}", ("GET",)),
        ("/api/artists/{artist_id}/tracks", ("GET",)),
    }),
    ("library", lambda: create_library_router(_none), {
        ("/api/library/refresh-references", ("POST",)),
        ("/api/library/reset", ("POST",)),
        ("/api/library/stats", ("GET",)),
    }),
    ("fingerprint_status", lambda: create_fingerprint_status_router(_none), {
        ("/api/library/fingerprints/status", ("GET",)),
        ("/api/tracks/{track_id}/fingerprint", ("GET",)),
    }),
    ("fingerprint_queue", lambda: create_fingerprint_queue_router(_none), {
        ("/api/similarity/fingerprint-queue/status", ("GET",)),
        ("/api/similarity/fingerprint-queue/enqueue/{track_id}", ("POST",)),
        ("/api/similarity/fingerprint-queue/enqueue-all", ("POST",)),
        ("/api/similarity/fingerprint-stats", ("GET",)),
    }),
    ("health", lambda: create_health_router(True), {
        ("/api/health", ("GET",)),
        ("/api/version", ("GET",)),
    }),
    ("cache_streamlined", lambda: create_streamlined_cache_router(_none), {
        ("/api/cache/clear", ("POST",)),
        ("/api/cache/health", ("GET",)),
        ("/api/cache/stats", ("GET",)),
        ("/api/cache/track/{track_id}", ("DELETE",)),
        ("/api/cache/track/{track_id}/status", ("GET",)),
    }),
    ("similarity_graph", lambda: create_similarity_graph_router(_none), {
        ("/api/similarity/graph", ("DELETE",)),
        ("/api/similarity/graph/build", ("POST",)),
        ("/api/similarity/graph/stats", ("GET",)),
    }),
]


@pytest.mark.parametrize(("name", "build", "expected"), _CASES, ids=[c[0] for c in _CASES])
def test_factory_registers_exactly_the_original_endpoints(name, build, expected):
    registered = {
        (route.path, tuple(sorted(route.methods)))  # type: ignore[attr-defined]
        for route in build().routes
    }

    assert registered == expected
