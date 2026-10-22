"""
The origin allow-list follows AURALIS_PORT (#5796).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`launch-auralis-web.py --port N` exports AURALIS_PORT=N and main.py binds it
(#4805), but `config/origins.py` kept its own literal 8765. The SPA is served
from the backend, so on any non-default port the page's origin was missing from
the CORS and WebSocket allow-lists and was rejected. main.py now imports the
constant instead of re-reading the variable, so the two cannot disagree.

BACKEND_PORT is read at import, so each case runs in a fresh interpreter.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"

_PROBE = (
    "import sys; sys.path.insert(0, %r);"
    "from config.origins import BACKEND_PORT, origin_matrix;"
    "print(BACKEND_PORT);"
    "print('\\n'.join(origin_matrix(('http', 'ws'))))"
) % str(_BACKEND)


def _probe(port):
    env = {k: v for k, v in os.environ.items() if k != "AURALIS_PORT"}
    if port is not None:
        env["AURALIS_PORT"] = port
    out = subprocess.run(
        [sys.executable, "-c", _PROBE], env=env, capture_output=True, text=True, check=True
    ).stdout.split()
    return int(out[0]), set(out[1:])


def test_default_port_is_unchanged():
    port, origins = _probe(None)
    assert port == 8765
    assert "http://localhost:8765" in origins


def test_allow_list_follows_a_custom_port():
    port, origins = _probe("9123")
    assert port == 9123
    assert {"http://localhost:9123", "http://127.0.0.1:9123", "ws://localhost:9123"} <= origins


@pytest.mark.parametrize("bad", ["not-a-number", "0", "-5"])
def test_a_malformed_port_falls_back_rather_than_crashing_startup(bad):
    port, _ = _probe(bad)
    assert port == 8765


def test_main_binds_the_same_constant():
    """main.py must import BACKEND_PORT, not call get_int_env on its own."""
    source = (_BACKEND / "main.py").read_text()
    assert "from config.origins import BACKEND_PORT" in source
    assert "_port = BACKEND_PORT" in source
    assert 'get_int_env("AURALIS_PORT"' not in source
