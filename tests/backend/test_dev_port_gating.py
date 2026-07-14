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
    # is_dev_mode() reads sys.argv + DEV_MODE fresh on each call.
    monkeypatch.setattr(sys, "argv", ["pytest"])
    monkeypatch.delenv("DEV_MODE", raising=False)


def _dev(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pytest"])
    monkeypatch.setenv("DEV_MODE", "1")


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
