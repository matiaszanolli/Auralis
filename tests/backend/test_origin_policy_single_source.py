# -*- coding: utf-8 -*-

"""
The CSP, CORS and WS allowlists share one host policy (#4712)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#3539 established that both `localhost` and `127.0.0.1` must be accepted —
browsers treat them as distinct origins — and fixed `cors_allowed_origins()`
and `build_ws_origins()` to iterate both. The hardcoded CSP literal was missed:
`connect-src 'self' ws://localhost:* http://localhost:*` had no `127.0.0.1`
form, so a page opened via `http://127.0.0.1:8765` had its WebSocket blocked by
CSP even though CORS and the handshake origin check both allowed it. The only
symptom is a console violation and no audio.

All three now derive from `config/origins.py`. These tests assert the header
content AND the set-equality between the three, so a future host addition that
edits only one of them fails here.
"""

import re
import sys
from pathlib import Path

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from config.globals import build_ws_origins  # noqa: E402
from config.middleware import cors_allowed_origins  # noqa: E402
from config.origins import (  # noqa: E402
    LOOPBACK_ORIGIN_HOSTS,
    csp_connect_src,
    origin_matrix,
)


def _hosts_in(sources: list[str]) -> set[str]:
    """Extract the host portion of every non-keyword source expression."""
    hosts = set()
    for src in sources:
        m = re.match(r"^[a-z]+://([^:/]+)", src)
        if m:
            hosts.add(m.group(1))
    return hosts


class TestCspConnectSrc:
    """Test-plan item 1: both host spellings for both schemes."""

    @pytest.mark.parametrize("scheme", ["ws", "http"])
    @pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
    def test_connect_src_permits_both_hosts_for_both_schemes(self, scheme, host):
        assert f"{scheme}://{host}:*" in csp_connect_src().split()

    def test_connect_src_keeps_self(self):
        assert "'self'" in csp_connect_src().split()

    def test_connect_src_covers_the_tls_dev_schemes(self):
        # #3897: a dev running Vite behind a TLS cert has an https/wss origin.
        # build_ws_origins() already emits those; the CSP omitting them would
        # be the same drift in a new place.
        sources = csp_connect_src().split()
        for host in LOOPBACK_ORIGIN_HOSTS:
            assert f"wss://{host}:*" in sources
            assert f"https://{host}:*" in sources


class TestPolicySetEquality:
    """Test-plan item 2: fails on future drift between the three allowlists."""

    def test_csp_host_set_equals_cors_host_set(self):
        assert _hosts_in(csp_connect_src().split()) == _hosts_in(cors_allowed_origins())

    def test_csp_host_set_equals_ws_host_set(self):
        ws_hosts = _hosts_in(sorted(build_ws_origins()))
        assert _hosts_in(csp_connect_src().split()) == ws_hosts

    def test_all_three_equal_the_declared_host_tuple(self):
        expected = set(LOOPBACK_ORIGIN_HOSTS)

        assert _hosts_in(csp_connect_src().split()) == expected
        assert _hosts_in(cors_allowed_origins()) == expected
        assert _hosts_in(sorted(build_ws_origins())) == expected


class TestExistingBehaviourUnchanged:
    """The CORS and WS allowlists must be behaviourally identical after the
    refactor — this issue only widens the CSP."""

    def test_cors_still_emits_http_and_https_only(self):
        schemes = {src.split("://", 1)[0] for src in cors_allowed_origins()}
        assert schemes == {"http", "https"}

    def test_ws_origins_still_include_file_scheme(self):
        # Packaged Electron renderers send `Origin: file://`.
        assert "file://" in build_ws_origins()

    def test_ws_origins_still_emit_all_four_schemes(self):
        schemes = {
            src.split("://", 1)[0] for src in build_ws_origins() if src != "file://"
        }
        assert schemes == {"http", "https", "ws", "wss"}

    def test_backend_port_present_in_both_allowlists(self):
        for host in LOOPBACK_ORIGIN_HOSTS:
            assert f"http://{host}:8765" in cors_allowed_origins()
            assert f"ws://{host}:8765" in build_ws_origins()


class TestSingleSourceOfTruth:
    """WIRING: all three allowlists must consume the shared helper."""

    def test_no_hardcoded_localhost_only_connect_src_remains(self):
        source = (Path(_BACKEND) / "config" / "middleware.py").read_text()

        assert "ws://localhost:* http://localhost:*" not in source, (
            "CSP connect-src hardcoded again — see #4712"
        )

    def test_the_three_consumers_all_import_from_origins(self):
        middleware = (Path(_BACKEND) / "config" / "middleware.py").read_text()
        globals_src = (Path(_BACKEND) / "config" / "globals.py").read_text()

        # CSP + CORS live in middleware.py, the WS allowlist in globals.py.
        assert "csp_connect_src" in middleware
        assert "origin_matrix" in middleware
        assert "origin_matrix" in globals_src

    def test_middleware_no_longer_respells_the_host_pair(self):
        """Adding a host should be one edit in origins.py, not three."""
        source = (Path(_BACKEND) / "config" / "middleware.py").read_text()
        # Strip comment lines: the file explains the both-spellings contract in
        # prose, which is documentation rather than a second copy of the policy.
        code = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        )

        assert '"127.0.0.1"' not in code, (
            "middleware.py re-spells the host list instead of using origin_matrix()"
        )

    def test_globals_loopback_hosts_stays_a_distinct_concept(self):
        """globals.LOOPBACK_HOSTS is NOT the origin host list and must not be
        folded into it: it answers "is this peer address loopback" for the
        empty-Origin check (#3845), so it includes `::1`, which is not a valid
        origin host without brackets."""
        from config.globals import LOOPBACK_HOSTS

        assert "::1" in LOOPBACK_HOSTS
        assert "::1" not in LOOPBACK_ORIGIN_HOSTS

    def test_matrix_is_ordered_and_covers_every_combination(self):
        matrix = origin_matrix(("http", "ws"))
        # 2 schemes x 2 hosts x 1 port (prod)
        assert len(matrix) == len(set(matrix))
        for scheme in ("http", "ws"):
            for host in LOOPBACK_ORIGIN_HOSTS:
                assert any(m.startswith(f"{scheme}://{host}:") for m in matrix)
