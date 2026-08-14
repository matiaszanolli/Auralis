"""
Loopback Origin Policy

The single source of truth for *which hosts* the backend considers its own.
Three allowlists express this one policy and had drifted apart:

  - ``middleware.cors_allowed_origins()`` — CORS ``Access-Control-Allow-Origin``
  - ``globals.build_ws_origins()``        — WebSocket handshake ``Origin`` check
  - the CSP ``connect-src`` directive     — what the *page* is allowed to open

#3539 fixed the first two to emit both ``localhost`` and ``127.0.0.1``, because
browsers treat them as distinct origins. The CSP literal was missed and still
listed only ``localhost`` (#4712), so a page opened via ``http://127.0.0.1:8765``
had its WebSocket blocked by CSP even though CORS and the handshake check both
allowed it — a hard failure whose only symptom is a console violation.

Adding a host must now be one edit here, not three edits in three files.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

# Both spellings of loopback. Browsers treat `localhost` and `127.0.0.1` as
# distinct origins, so every allowlist derived from this must carry both
# (#3539). This is deliberately NOT globals.LOOPBACK_HOSTS, which answers a
# different question (is this *peer address* loopback, for the empty-Origin
# check in #3845) and therefore includes `::1` — a bare IPv6 literal is not a
# valid origin host without brackets.
LOOPBACK_ORIGIN_HOSTS: tuple[str, ...] = ("localhost", "127.0.0.1")

# The backend's own port. Always allowed: it serves the SPA in packaged builds.
BACKEND_PORT = 8765

# Vite dev-server ports. Legitimate only in development — a packaged build never
# serves the frontend from them (#4350).
DEV_PORTS: tuple[int, ...] = tuple(range(3000, 3007))


def allowed_origin_ports() -> list[int]:
    """Ports the app may legitimately be served from, dev-gated per #4350.

    Callers must not cache the result: is_dev_mode() is read fresh so tests can
    monkeypatch it, and `ALLOWED_WS_ORIGINS` freezes its own snapshot at import
    time deliberately (see globals.py).
    """
    from .app import is_dev_mode
    return (list(DEV_PORTS) if is_dev_mode() else []) + [BACKEND_PORT]


def origin_matrix(schemes: tuple[str, ...]) -> list[str]:
    """The scheme x host x port matrix, in a stable order.

    Args:
        schemes: URL schemes to emit, e.g. ``("http", "https")`` for CORS or
            ``("http", "https", "ws", "wss")`` for the WS handshake check.
    """
    ports = allowed_origin_ports()
    return [
        f"{scheme}://{host}:{port}"
        for scheme in schemes
        for host in LOOPBACK_ORIGIN_HOSTS
        for port in ports
    ]


def csp_connect_src() -> str:
    """The CSP ``connect-src`` source list.

    Unlike the CORS and WS allowlists this uses a wildcard port (`host:*`)
    rather than enumerating `allowed_origin_ports()`. That is the pre-existing
    behaviour and is kept deliberately: CSP constrains what the *page* may
    open, and the page is only ever served from a loopback origin we control,
    so the host restriction is the part carrying the weight. Enumerating ports
    here would also make the header dev-mode-dependent, which it has never been.

    All four schemes are emitted, matching build_ws_origins(): #3897 established
    that a dev running Vite behind a TLS cert has an `https://`/`wss://` origin,
    and a CSP that omits them recreates exactly the drift this module exists to
    prevent.
    """
    sources = ["'self'"]
    sources.extend(
        f"{scheme}://{host}:*"
        for scheme in ("ws", "wss", "http", "https")
        for host in LOOPBACK_ORIGIN_HOSTS
    )
    return " ".join(sources)


__all__ = [
    'LOOPBACK_ORIGIN_HOSTS',
    'BACKEND_PORT',
    'DEV_PORTS',
    'allowed_origin_ports',
    'origin_matrix',
    'csp_connect_src',
]
