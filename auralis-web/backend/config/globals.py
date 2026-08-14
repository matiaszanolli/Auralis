"""
Global State Management

Centralized global variable declarations and shared utilities like ConnectionManager.
These are initialized during application startup and used throughout the backend.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Allowed origins for WebSocket connections — single authoritative allowlist
# (fixes #2413: cross-origin hijacking, and #3524 / BE-NEW-66: prior
# system.py prefix-based pre-check disagreed with this strict allowlist on
# e.g. `file://` Electron origins). Browser clients send the Origin header;
# non-browser clients (native apps, tests) may not.
#
# Generated programmatically over the same host x port matrix as CORS
# (see config/middleware.py), plus `file://` for packaged Electron builds
# whose renderer Origin header is `file://`.
def build_ws_origins() -> frozenset[str]:
    """Build the allowed WebSocket origins.

    The Vite dev ports (3000-3006) are only legitimate in dev — gate them on
    is_dev_mode() so a packaged build won't accept WS upgrades from those origins
    (#4350). 8765 (the backend) and file:// (Electron renderer) are always
    allowed. Shares the dev-gating contract with middleware.cors_allowed_origins.
    """
    from .app import is_dev_mode
    ports = (list(range(3000, 3007)) if is_dev_mode() else []) + [8765]
    return frozenset(
        {
            f"{scheme}://{host}:{port}"
            for scheme in ("http", "https", "ws", "wss")
            for host in ("localhost", "127.0.0.1")
            for port in ports
        }
        | {"file://"}
    )


# Frozen at import time: dev/prod mode is fixed for the process lifetime (set by
# the launcher via --dev / AURALIS_DEV_MODE, #4802), so the runtime WS origin check reads this.
ALLOWED_WS_ORIGINS = build_ws_origins()

# Hosts considered loopback — empty-Origin connections are allowed only from
# these addresses so non-browser local processes on non-loopback interfaces
# cannot bypass the origin check (fixes #3845). Public (not module-private)
# because config.middleware.OriginCheckMiddleware reuses it for the REST
# equivalent of this same check (#4893).
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

# Per-client ceiling on a single broadcast send (#4581). Generous for a
# loopback socket a healthy client is draining, short enough that a wedged
# client cannot hold up transport commands for a user-visible interval.
BROADCAST_SEND_TIMEOUT = 2.0


class WebSocketOriginRejected(Exception):
    """Raised by `ConnectionManager.connect` when the handshake is denied.

    #4703: rejection used to be a bare `return` after `close(1008)`, and
    `setup_connection` ignored the result — so the endpoint ran a full
    connection lifecycle on a socket that was never accepted: a connection id,
    a spawned heartbeat task that sleeps up to 30 s before its first send
    fails, two swallowed initial pushes, and a whole teardown pass.

    Not an auth bypass — the handshake is denied before `accept()`, so no client
    message can ever be exchanged. The cost is wasted work plus the latent
    hazard that the single authoritative origin check had no way to stop the
    handler, so anything added between `setup_connection` and the receive loop
    would have run for rejected origins too.

    An exception rather than a bool return (which #3524 made load-bearing by
    consolidating the origin policy here): a bool can be ignored by the next
    caller exactly as it was, an exception cannot be silently dropped.
    """


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.

    Tracks active connections and broadcasts messages to all connected clients.
    """

    def __init__(self) -> None:
        """Initialize connection manager with empty connections list."""
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection.

        Validates the Origin header to prevent cross-origin hijacking attacks.
        Rejects connections from untrusted origins (fixes #2413).

        Args:
            websocket: WebSocket connection to register

        Raises:
            WebSocketOriginRejected: the handshake was denied and the socket
                closed with 1008. Both rejection branches signal identically,
                and neither reaches `accept()` (#4703).
        """
        # Check Origin header for security (CORS does not apply to WebSocket upgrades).
        origin = websocket.headers.get("origin", "").lower()
        if origin:
            # Non-empty Origin: must be in the allowlist (fixes #2413).
            if origin not in ALLOWED_WS_ORIGINS:
                logger.warning(f"WebSocket connection rejected: untrusted origin {origin!r}")
                await websocket.close(code=1008)  # Policy Violation
                raise WebSocketOriginRejected(f"untrusted origin {origin!r}")
        else:
            # Empty Origin: allow only from loopback so non-browser processes
            # on non-loopback interfaces cannot bypass the check (fixes #3845).
            client_host = (websocket.client.host if websocket.client else "").lower()
            if client_host not in LOOPBACK_HOSTS:
                logger.warning(
                    f"WebSocket connection rejected: empty Origin from non-loopback host {client_host!r}"
                )
                await websocket.close(code=1008)  # Policy Violation
                raise WebSocketOriginRejected(
                    f"empty Origin from non-loopback host {client_host!r}"
                )

        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        client = websocket.client
        client_id = f"{client.host}:{client.port}" if client else "unknown"
        logger.info(f"WebSocket connected from {client_id}. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            websocket: WebSocket connection to unregister
        """
        client = websocket.client
        client_id = f"{client.host}:{client.port}" if client else "unknown"
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                logger.info(f"WebSocket disconnected from {client_id}. Total connections: {len(self.active_connections)}")
            else:
                logger.debug(f"WebSocket disconnect called for {client_id} but connection not in list (already removed)")

    async def _send_to(self, connection: WebSocket, message_json: str) -> None:
        """Send one already-encoded frame to one client, bounded by a timeout.

        #4581: Starlette applies backpressure, so a client that stops draining
        its socket makes send_text block until the OS buffer clears — which
        could be forever for a suspended Electron renderer or a half-open TCP
        connection. Every caller awaiting broadcast() inherited that stall, and
        PlaybackService held _playback_lock across it, freezing all transport
        controls. A client that cannot accept a frame within the timeout is
        treated exactly like one that raised: evicted.
        """
        await asyncio.wait_for(
            connection.send_text(message_json),
            timeout=BROADCAST_SEND_TIMEOUT,
        )

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcast message to all connected clients.

        Sends run concurrently (#3867): a serial loop made every client wait out
        the slowest one, so a single wedged client added BROADCAST_SEND_TIMEOUT
        to the latency of every client behind it in the list. With gather, the
        whole broadcast costs one timeout at worst regardless of client count.

        Automatically removes stale connections that fail to receive messages,
        including ones that are merely *stuck* rather than errored.

        Args:
            message: Dictionary message to broadcast (will be JSON encoded)
        """
        stale_connections: list[WebSocket] = []

        async with self._lock:
            connections_snapshot = list(self.active_connections)

        if not connections_snapshot:
            return

        message_json = json.dumps(message)

        results = await asyncio.gather(
            *(self._send_to(connection, message_json) for connection in connections_snapshot),
            return_exceptions=True,
        )

        for connection, result in zip(connections_snapshot, results):
            if not isinstance(result, BaseException):
                continue
            stale_connections.append(connection)
            if isinstance(result, TimeoutError):
                logger.warning(
                    f"WebSocket send exceeded {BROADCAST_SEND_TIMEOUT}s — "
                    f"marking connection stale for removal"
                )
            else:
                logger.debug(f"Marking stale connection for removal: {result}")

        if stale_connections:
            async with self._lock:
                for stale in stale_connections:
                    if stale in self.active_connections:
                        self.active_connections.remove(stale)
            logger.info(f"Removed {len(stale_connections)} stale connection(s). Active: {len(self.active_connections)}")


# ---------------------------------------------------------------------------
# Component registry
# ---------------------------------------------------------------------------
#
# #4578: this module used to define its own `globals_dict = create_globals_dict()`
# alongside the one `main.py` builds. Only main.py's was ever populated by
# startup, so anything reading this module's copy saw a permanently-empty
# registry. `_default_get_fingerprints_repository()` did exactly that, which is
# why the #3836 Tier-1 fingerprint fix shipped but never took effect: the key it
# looked up ('repository_factory') was not even declared here.
#
# There is now exactly one registry object in the process. main.py builds it and
# registers it here; readers go through get_component_registry(), which resolves
# at call time — a module-level `globals_dict` would be import-bound and would
# silently re-create the same class of bug for anyone using `from ... import`.

_component_registry: dict[str, Any] | None = None


def set_component_registry(registry: dict[str, Any]) -> None:
    """Register the process-wide component registry (called once, from main.py).

    Startup mutates this same object in place, so readers registered before
    startup completes still observe components as they are populated.
    """
    global _component_registry
    _component_registry = registry


def get_component_registry() -> dict[str, Any] | None:
    """Return the process-wide component registry, or None if unregistered.

    None is the legitimate state in unit tests that never build the app, so
    callers treat it as "component unavailable" rather than an error.
    """
    return _component_registry
