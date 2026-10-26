"""
Cross-site GETs under /api need a trusted Origin or Referer (#6158)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OriginCheckMiddleware gated only POST/PUT/DELETE/PATCH, but some GET routes are
expensive or have side effects (mastering-recommendation analysis, fingerprint
enqueue, lyrics persistence) and a hostile page can fire any GET blind with
``<img src>`` or a no-cors fetch. Such a request carries
``Sec-Fetch-Site: cross-site`` (or ``same-site`` from another local port) and no
Origin; it is refused unless its Referer names a trusted origin. Requests that
carry no Sec-Fetch-Site (curl, Electron's main process, tests) are unchanged.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import setup_middleware  # noqa: E402

TRUSTED = "http://localhost:8765"
HOSTILE = "https://evil.example"


@pytest.fixture
def app():
    application = FastAPI()
    setup_middleware(application)

    @application.get("/api/tracks/{track_id}/fingerprint")
    async def fingerprint(track_id: int):
        return {"queued": track_id}

    @application.get("/health")
    async def health():
        return {"ok": True}

    return application


async def _get(app, path="/api/tracks/1/fingerprint", **headers):
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path, headers=headers)


@pytest.mark.asyncio
@pytest.mark.parametrize("site", ["cross-site", "same-site"])
async def test_blind_cross_site_get_is_rejected(app, site):
    response = await _get(app, **{"Sec-Fetch-Site": site})

    assert response.status_code == 403
    assert response.json() == {"detail": "Untrusted origin"}


@pytest.mark.asyncio
async def test_hostile_referer_and_hostile_origin_are_rejected(app):
    assert (await _get(app, **{"Sec-Fetch-Site": "cross-site", "Referer": HOSTILE + "/page"})).status_code == 403
    assert (await _get(app, **{"Sec-Fetch-Site": "cross-site", "Origin": HOSTILE})).status_code == 403


@pytest.mark.asyncio
async def test_trusted_page_on_another_port_or_host_still_works(app):
    """A dev page on 127.0.0.1:3001 loading <img> from the backend is cross-site
    with no Origin but a trusted Referer; a CORS fetch carries a trusted Origin."""
    for header in ({"Referer": "http://127.0.0.1:8765/library"}, {"Origin": TRUSTED}):
        response = await _get(app, **{"Sec-Fetch-Site": "cross-site", **header})
        assert response.status_code == 200, header


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{}, {"Sec-Fetch-Site": "same-origin"}, {"Sec-Fetch-Site": "none"}])
async def test_same_origin_and_non_browser_requests_are_unaffected(app, headers):
    assert (await _get(app, **headers)).status_code == 200


@pytest.mark.asyncio
async def test_paths_outside_api_are_not_gated(app):
    assert (await _get(app, "/health", **{"Sec-Fetch-Site": "cross-site"})).status_code == 200


@pytest.mark.asyncio
async def test_preflight_is_not_blocked(app):
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/tracks/1/fingerprint",
            headers={
                "Origin": TRUSTED, "Sec-Fetch-Site": "cross-site",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
