"""NoCacheMiddleware keeps entry points uncached but lets hashed bundles cache (#5071).

It forced `no-store` on every non-API .html/.js/.css, including Vite's
content-hashed bundles under /assets/, whose URL changes on every build, so the
hashing's caching benefit was thrown away. The only place a stale copy hurts is the
entry point (/ and *.html) and any un-hashed script.
"""

import sys
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import NoCacheMiddleware  # noqa: E402

NO_STORE = "no-cache, no-store, must-revalidate, max-age=0"
IMMUTABLE = "public, max-age=31536000, immutable"


def _client():
    async def ok(request):
        return PlainTextResponse("x")

    async def missing(request):
        return PlainTextResponse("nope", status_code=404)

    paths = ["/", "/index.html", "/assets/index-abc123.js", "/assets/index-abc123.css",
             "/sw.js", "/other.css", "/assets/logo.svg", "/api/thing.js", "/ws/thing.js"]
    app = Starlette(routes=[Route(p, ok) for p in paths] + [Route("/assets/gone-ffff.js", missing)])
    app.add_middleware(NoCacheMiddleware)
    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/index.html", "/sw.js", "/other.css"])
def test_entry_points_and_unhashed_scripts_stay_no_store(path):
    r = _client().get(path)
    assert r.headers["cache-control"] == NO_STORE
    assert r.headers["pragma"] == "no-cache" and r.headers["expires"] == "0"


@pytest.mark.parametrize("path", ["/assets/index-abc123.js", "/assets/index-abc123.css"])
def test_hashed_bundles_are_cacheable_forever(path):
    r = _client().get(path)
    assert r.headers["cache-control"] == IMMUTABLE
    assert "pragma" not in r.headers


def test_a_missing_hashed_bundle_is_not_made_immutable():
    r = _client().get("/assets/gone-ffff.js")
    assert r.status_code == 404
    assert "immutable" not in r.headers.get("cache-control", "")


@pytest.mark.parametrize("path", ["/assets/logo.svg", "/api/thing.js", "/ws/thing.js"])
def test_other_paths_are_left_alone(path):
    assert "cache-control" not in _client().get(path).headers
