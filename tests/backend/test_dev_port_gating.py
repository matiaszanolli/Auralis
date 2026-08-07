"""Regression tests for dev-port CORS/WS allowlist gating (#4350).

The Vite dev ports (3000-3006) are only legitimate in development. A packaged
build never serves the frontend from them, so both the CORS allow-origins list
and the WebSocket origin allowlist must exclude them when is_dev_mode() is false,
leaving only the backend port (8765) and file:// (Electron renderer).
"""

import sys
from pathlib import Path

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from config.middleware import cors_allowed_origins  # noqa: E402
from config.globals import build_ws_origins  # noqa: E402


def _prod(monkeypatch):
    # is_dev_mode() reads sys.argv + AURALIS_DEV_MODE fresh on each call
    # (#4802 — renamed from the unnamespaced DEV_MODE).
    monkeypatch.setattr(sys, "argv", ["pytest"])
    monkeypatch.delenv("AURALIS_DEV_MODE", raising=False)


def _dev(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pytest"])
    monkeypatch.setenv("AURALIS_DEV_MODE", "1")


def test_cors_excludes_dev_ports_in_production(monkeypatch):
    _prod(monkeypatch)
    origins = cors_allowed_origins()
    assert "http://localhost:8765" in origins
    assert "http://127.0.0.1:8765" in origins
    for port in range(3000, 3007):
        assert f"http://localhost:{port}" not in origins
        assert f"http://127.0.0.1:{port}" not in origins


def test_cors_includes_dev_ports_in_dev(monkeypatch):
    _dev(monkeypatch)
    origins = cors_allowed_origins()
    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3006" in origins
    assert "http://localhost:8765" in origins


def test_ws_origins_exclude_dev_ports_in_production(monkeypatch):
    _prod(monkeypatch)
    origins = build_ws_origins()
    assert "http://localhost:8765" in origins
    assert "wss://127.0.0.1:8765" in origins
    assert "file://" in origins
    for port in range(3000, 3007):
        assert f"http://localhost:{port}" not in origins
        assert f"ws://localhost:{port}" not in origins


def test_ws_origins_include_dev_ports_in_dev(monkeypatch):
    _dev(monkeypatch)
    origins = build_ws_origins()
    assert "http://localhost:3000" in origins
    assert "ws://127.0.0.1:3006" in origins
    assert "file://" in origins
    assert "http://localhost:8765" in origins


# ---------------------------------------------------------------------------
# HTTPS scheme coverage (#3897)
#
# Both allowlists were built from http-only scheme tuples. A dev running Vite
# behind a TLS cert (needed for secure-context features such as service
# workers) has a page origin of `https://localhost:3000`; the WS upgrade then
# carries that Origin and was rejected with code 1008, and CORS preflight
# failed for the same reason. build_ws_origins() was fixed during the #4350
# rework; cors_allowed_origins() was still http-only.
# ---------------------------------------------------------------------------


def test_cors_includes_https_for_dev_ports(monkeypatch):
    _dev(monkeypatch)
    origins = cors_allowed_origins()
    assert "https://localhost:3000" in origins
    assert "https://127.0.0.1:3000" in origins
    assert "https://localhost:8765" in origins


def test_cors_includes_https_in_production(monkeypatch):
    _prod(monkeypatch)
    origins = cors_allowed_origins()
    assert "https://localhost:8765" in origins
    assert "https://127.0.0.1:8765" in origins


def test_cors_https_is_still_dev_port_gated(monkeypatch):
    """Adding https must not smuggle the dev ports back into production."""
    _prod(monkeypatch)
    origins = cors_allowed_origins()
    for port in range(3000, 3007):
        assert f"https://localhost:{port}" not in origins
        assert f"https://127.0.0.1:{port}" not in origins


def test_cors_omits_websocket_schemes(monkeypatch):
    """An HTTP Origin header always carries the page scheme, so ws:// entries
    could never match a preflight — they would be dead weight, not coverage."""
    _dev(monkeypatch)
    origins = cors_allowed_origins()
    assert not [o for o in origins if o.startswith(("ws://", "wss://"))]


def test_ws_origins_cover_https_and_wss(monkeypatch):
    _dev(monkeypatch)
    origins = build_ws_origins()
    for origin in (
        "https://localhost:3000",
        "wss://localhost:3000",
        "https://127.0.0.1:8765",
        "wss://127.0.0.1:8765",
    ):
        assert origin in origins


def test_both_allowlists_agree_on_http_schemes(monkeypatch):
    """The two lists share a dev-gating contract; they must not drift apart on
    scheme coverage either, which is how this gap survived the #4350 rework."""
    _dev(monkeypatch)
    cors = {o for o in cors_allowed_origins()}
    ws = {o for o in build_ws_origins() if o.startswith(("http://", "https://"))}
    assert cors == ws
