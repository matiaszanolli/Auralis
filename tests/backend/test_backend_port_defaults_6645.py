"""
Every default for the backend port agrees with the backend's own (#6645)

config/origins.py's BACKEND_PORT (AURALIS_PORT, default 8765) is the authority. The places that
cannot import it (the launcher runs before the backend's import path exists; the Vite config and
the browser bundle are TypeScript; the sandboxed Electron preload cannot require modules) keep a
copy of the default, which this test holds equal so changing the port is one edit plus a red test
at every copy it missed.
"""

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

_COPIES = [
    ("auralis-web/backend/config/origins.py", r'get_int_env\("AURALIS_PORT",\s*(\d+)\)'),
    ("launch-auralis-web.py", r"^BACKEND_PORT = (\d+)$"),
    ("auralis-web/frontend/vite.config.mts", r"process\.env\.AURALIS_PORT \?\? '(\d+)'"),
    ("auralis-web/frontend/src/config/api.ts", r"VITE_BACKEND_PORT \?\? '(\d+)'"),
    ("desktop/url-safety.js", r"^const APP_PORT = (\d+);"),
    ("desktop/preload.js", r"^const APP_ORIGIN = 'http://127\.0\.0\.1:(\d+)';"),
]


def _default(rel: str, pattern: str) -> int:
    match = re.search(pattern, (_ROOT / rel).read_text(), re.M)
    assert match, f"no backend-port default matching {pattern!r} in {rel}"
    return int(match.group(1))


@pytest.mark.parametrize(("rel", "pattern"), _COPIES[1:], ids=[rel for rel, _ in _COPIES[1:]])
def test_copy_matches_the_backend_default(rel, pattern):
    assert _default(rel, pattern) == _default(*_COPIES[0])


def test_launcher_and_vite_take_the_port_from_one_place():
    launcher = (_ROOT / "launch-auralis-web.py").read_text()
    vite = (_ROOT / "auralis-web/frontend/vite.config.mts").read_text()

    assert "port: int = BACKEND_PORT" in launcher and "default=BACKEND_PORT" in launcher
    assert "'import.meta.env.VITE_BACKEND_PORT': JSON.stringify(backendPort)" in vite
    assert vite.count("8765") == 1
