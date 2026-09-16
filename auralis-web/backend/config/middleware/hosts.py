"""
Allowed Origins and Hosts

The CORS allow-origins list and the trusted Host header values. Split out
of config/middleware.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys

from ..origins import LOOPBACK_ORIGIN_HOSTS, origin_matrix


def cors_allowed_origins() -> list[str]:
    """Build the CORS allow-origins list.

    Both `localhost` and `127.0.0.1` are emitted for every port — browsers treat
    them as distinct origins, so a dev opening the app via the IP form on an alt
    port (e.g. 127.0.0.1:3001) would otherwise be blocked by CORS preflight
    (#3539 / BE-NEW-81). The Vite dev ports (3000-3006) are only legitimate in
    dev; a packaged build never serves the frontend from them, so they are
    included only when is_dev_mode() (#4350). Port 8765 (the backend itself) is
    always allowed. Shares the dev-gating contract with globals.ALLOWED_WS_ORIGINS.

    Both http and https are emitted (#3897). A dev running Vite behind a TLS
    cert — needed for secure-context features like service workers — has a page
    origin of `https://localhost:3000`, which this list would otherwise reject
    at CORS preflight. globals.build_ws_origins() already covers the https/wss
    schemes; this list was the remaining half of that gap.

    Only http/https appear here, not ws/wss: an Origin header for an HTTP
    request always carries the *page* scheme, so a `ws://` entry could never
    match a CORS preflight.

    The host x port matrix itself lives in config/origins.py — shared with
    build_ws_origins() and the CSP connect-src directive so the three cannot
    drift apart again (#4712).
    """
    return origin_matrix(("http", "https"))


# Hosts a browser can legitimately put in the Host header for this backend.
#
# Starlette's TrustedHostMiddleware strips the port before matching
# (`headers.get("host", "").split(":")[0]`), so these are bare hostnames. The
# issue proposed entries like "localhost:8765" — those could never match, since
# the port is gone by the time the comparison happens.
#
# No "[::1]": the same split(":") leaves "[" for an IPv6 literal, so a bracketed
# address cannot be matched at all. It does not need to be — main.py binds
# 127.0.0.1, so the v6 loopback never reaches this process.
#
# Sourced from config/origins.py rather than re-spelled here: this was the
# fourth independent copy of the same both-spellings host policy, alongside
# CORS, the WS allowlist and the CSP (#4712 / #3539). A new loopback spelling
# must be trusted in the Host header for the same reason it must be allowed as
# an origin, so the coupling is intended.
_TRUSTED_HOSTS: tuple[str, ...] = LOOPBACK_ORIGIN_HOSTS

# Starlette's TestClient sends `Host: testserver` by default, and several
# suites drive the ASGI app through httpx with base_url="http://test". Neither
# is resolvable as a public domain (both are single-label, so a browser cannot
# be induced to send them for a rebound address), but they are still test
# scaffolding and are kept out of the shipped allowlist.
_TEST_HOSTS: tuple[str, ...] = ("testserver", "test")


def trusted_hosts(include_test_hosts: bool | None = None) -> list[str]:
    """Build the allowed Host header values (#4353).

    DNS-rebinding defence in depth: a page on attacker.com rebound to 127.0.0.1
    reaches this backend with `Host: attacker.com`. Validating the header
    rejects it before any handler runs.

    Args:
        include_test_hosts: Force the test hosts in or out. Defaults to
            autodetecting pytest, so production never carries them; passing
            False is how the test suite asserts that.
    """
    if include_test_hosts is None:
        include_test_hosts = "pytest" in sys.modules
    hosts = list(_TRUSTED_HOSTS)
    if include_test_hosts:
        hosts.extend(_TEST_HOSTS)
    return hosts
