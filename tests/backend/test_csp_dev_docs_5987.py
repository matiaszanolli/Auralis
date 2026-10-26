"""
Dev-mode /api/docs and /api/redoc get a CSP that admits their CDN assets (#5987)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

FastAPI's Swagger UI / ReDoc HTML loads its bundles from cdn.jsdelivr.net, which
the blanket ``script-src 'self' 'unsafe-inline'`` excluded, so both pages
rendered blank under ``--dev``. The CSP is widened for those two paths only, and
only in dev mode; production keeps the strict policy.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import SecurityHeadersMiddleware  # noqa: E402

_CDN = "https://cdn.jsdelivr.net"


def _app() -> FastAPI:
    app = FastAPI(docs_url="/api/docs", redoc_url="/api/redoc")

    @app.get("/")
    async def root():
        return {}

    app.add_middleware(SecurityHeadersMiddleware)
    return app


async def _csp(path: str) -> str:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=_app()), base_url="http://localhost:8765"
    ) as client:
        response = await client.get(path)
    return response.headers["content-security-policy"]


def _directive(csp: str, name: str) -> str:
    return next(d for d in csp.split("; ") if d.startswith(f"{name} "))


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/docs", "/api/redoc"])
async def test_dev_docs_pages_allow_the_cdn(monkeypatch, path):
    monkeypatch.setenv("AURALIS_DEV_MODE", "1")

    csp = await _csp(path)

    assert _CDN in _directive(csp, "script-src")
    assert _CDN in _directive(csp, "style-src")
    assert "blob:" in _directive(csp, "worker-src")
    # ReDoc's own web fonts (the app bundles its fonts, #6060).
    assert "https://fonts.googleapis.com" in _directive(csp, "style-src")
    assert "https://fonts.gstatic.com" in _directive(csp, "font-src")


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/docs", "/api/redoc", "/"])
async def test_non_dev_csp_never_names_the_cdn(monkeypatch, path):
    monkeypatch.delenv("AURALIS_DEV_MODE", raising=False)

    csp = await _csp(path)

    assert _CDN not in csp
    assert "worker-src" not in csp
    # The app bundles Asap and JetBrains Mono (#6060): no font CDN is allowlisted.
    assert "fonts.googleapis.com" not in csp
    assert "fonts.gstatic.com" not in csp


@pytest.mark.asyncio
async def test_dev_mode_keeps_the_strict_csp_off_the_docs_paths(monkeypatch):
    monkeypatch.setenv("AURALIS_DEV_MODE", "1")

    csp = await _csp("/")

    assert _CDN not in csp
