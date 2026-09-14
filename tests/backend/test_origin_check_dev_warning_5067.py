"""
Regression: OriginCheckMiddleware must not re-evaluate is_dev_mode() per
request (#5067)

`OriginCheckMiddleware.dispatch()` used to call `cors_allowed_origins()` —
which calls `is_dev_mode()` — on every state-changing REST request. When dev
mode is active via the AURALIS_DEV_MODE env var, `is_dev_mode()` logs a
5-line warning meant as a one-shot boot notice; calling it per request turned
that into per-request log spam. The fix caches the allowlist once at
middleware construction (`__init__`), mirroring how `CORSMiddleware`'s own
setup already resolves the same list once at app-construction time.

`is_dev_mode()` itself must stay fully dynamic — #4802's own tests
(`test_dev_mode_env_var_namespaced_4802.py`) call it directly and expect a
fresh warning on every call — so this test asserts the warning is not
triggered repeatedly *through OriginCheckMiddleware*, not that
`is_dev_mode()` was changed to warn once globally.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.middleware import OriginCheckMiddleware, setup_middleware  # noqa: E402

TRUSTED_ORIGIN = "http://localhost:8765"


@pytest.fixture
def dev_mode_app(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setenv("AURALIS_DEV_MODE", "1")

    application = FastAPI()
    setup_middleware(application)

    @application.post("/api/player/queue/clear")
    async def clear_queue():
        return {"ok": True}

    return application


@pytest.mark.asyncio
async def test_dev_mode_warning_not_repeated_per_request(dev_mode_app, caplog):
    transport = ASGITransport(app=dev_mode_app)
    with caplog.at_level(logging.WARNING, logger="config.app"):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(5):
                resp = await client.post(
                    "/api/player/queue/clear", headers={"Origin": TRUSTED_ORIGIN}
                )
                assert resp.status_code == 200

    dev_mode_warnings = [
        r for r in caplog.records if "AURALIS_DEV_MODE" in r.message
    ]
    assert len(dev_mode_warnings) <= 1, (
        f"expected the dev-mode warning at most once across 5 requests, "
        f"got {len(dev_mode_warnings)} — is_dev_mode() is being re-evaluated "
        f"per request instead of cached at middleware construction"
    )


def test_middleware_caches_origins_at_construction(monkeypatch):
    """WIRING: __init__ resolves the allowlist once; dispatch must not call
    cors_allowed_origins() again."""
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.delenv("AURALIS_DEV_MODE", raising=False)

    application = FastAPI()
    middleware = OriginCheckMiddleware(application)

    assert isinstance(middleware._cached_origins, frozenset)
    assert "http://localhost:8765" in middleware._cached_origins


@pytest.mark.asyncio
async def test_cached_origins_still_agree_with_cors_middleware(monkeypatch):
    """Acceptance criterion: OriginCheckMiddleware and CORSMiddleware must
    still agree on the same origin list (no regression of the shared
    contract #4712 established)."""
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.delenv("AURALIS_DEV_MODE", raising=False)

    from config.middleware import cors_allowed_origins

    application = FastAPI()
    setup_middleware(application)

    origin_middleware = next(
        m for m in application.user_middleware if m.cls is OriginCheckMiddleware
    )
    # Build it the same way Starlette's middleware stack construction would.
    instance = origin_middleware.cls(application, **origin_middleware.kwargs)
    assert instance._cached_origins == frozenset(cors_allowed_origins())
