"""Host-header validation / DNS-rebinding defence in depth (#4353).

Nothing validated the HTTP Host header, so a page on attacker.com rebound to
127.0.0.1 reached the backend and its requests were served normally. The
WebSocket already had an Origin allowlist and JSON POSTs force a CORS preflight,
so the residual window was CORS-"simple" requests — but "the response is
unreadable cross-origin" is not the same as "the request did not happen".

TrustedHostMiddleware closes it. Two details of Starlette's implementation drive
the shape of the allowlist and are pinned below, because getting either wrong
produces a middleware that looks installed but matches nothing:

  1. it strips the port before comparing (`host.split(":")[0]`), so entries must
     be bare hostnames — the "localhost:8765" form the issue proposed can never
     match;
  2. it also runs for `websocket` scopes, so the WS handshake is covered too.
"""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from config.middleware import setup_middleware, trusted_hosts  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """A minimal app carrying the real middleware stack."""
    app = FastAPI()
    setup_middleware(app)

    @app.get("/probe")
    async def probe() -> dict[str, str]:
        return {"ok": "yes"}

    # raise_server_exceptions=False so a 4xx is returned rather than re-raised.
    return TestClient(app, raise_server_exceptions=False)


class TestForeignHostRejected:
    @pytest.mark.parametrize(
        "host",
        [
            "attacker.com",
            "evil.example.com",
            "auralis.attacker.com",       # subdomain of an attacker domain
            "localhost.attacker.com",     # prefix that merely looks loopback
            "127.0.0.1.attacker.com",
        ],
    )
    def test_rejects_foreign_host(self, client, host):
        response = client.get("/probe", headers={"Host": host})
        assert response.status_code == 400

    def test_rejects_empty_host(self, client):
        response = client.get("/probe", headers={"Host": ""})
        assert response.status_code == 400

    def test_rejection_still_carries_the_security_headers(self, client):
        """The 400 is wrapped by SecurityHeadersMiddleware, matching the #3843
        ordering decision for rate-limit 429s. If TrustedHost were registered
        outermost this would fail."""
        response = client.get("/probe", headers={"Host": "attacker.com"})
        assert response.status_code == 400
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"


class TestLoopbackHostsAccepted:
    @pytest.mark.parametrize(
        "host",
        [
            "localhost",
            "127.0.0.1",
            "localhost:8765",       # port is stripped before matching
            "127.0.0.1:8765",
            "localhost:3000",       # Vite dev origin (changeOrigin rewrites it)
        ],
    )
    def test_accepts_loopback_host(self, client, host):
        response = client.get("/probe", headers={"Host": host})
        assert response.status_code == 200
        assert response.json() == {"ok": "yes"}


class TestAllowlistShape:
    def test_entries_are_bare_hostnames_without_ports(self):
        """Starlette compares against a port-stripped host, so a ':port' entry
        is dead weight that can never match."""
        for host in trusted_hosts(include_test_hosts=False):
            assert ":" not in host, f"{host!r} carries a port and can never match"

    def test_production_allowlist_is_loopback_only(self):
        """The test hosts must not ship."""
        assert trusted_hosts(include_test_hosts=False) == ["localhost", "127.0.0.1"]

    def test_test_hosts_are_present_while_running_under_pytest(self):
        """Autodetection has to actually fire, or the whole backend suite —
        which drives the app as Host: testserver — would 400."""
        assert "testserver" in trusted_hosts()
        assert "test" in trusted_hosts()

    def test_no_wildcard_entry(self):
        """A '*' would disable the middleware entirely (Starlette short-circuits
        on allow_any) while still looking installed."""
        assert "*" not in trusted_hosts()
        assert "*" not in trusted_hosts(include_test_hosts=False)


class TestWiring:
    def test_middleware_is_registered_not_merely_imported(self):
        """The issue's WIRING check: it must be added, not just imported."""
        from starlette.middleware.trustedhost import TrustedHostMiddleware

        app = FastAPI()
        setup_middleware(app)
        assert any(m.cls is TrustedHostMiddleware for m in app.user_middleware)

    def test_registered_with_a_real_allowlist(self):
        """allowed_hosts=None or ['*'] would make it a no-op."""
        from starlette.middleware.trustedhost import TrustedHostMiddleware

        app = FastAPI()
        setup_middleware(app)
        entry = next(m for m in app.user_middleware if m.cls is TrustedHostMiddleware)
        allowed = entry.kwargs["allowed_hosts"]
        assert allowed
        assert "*" not in allowed
