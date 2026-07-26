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
# the launcher via --dev / DEV_MODE), so the runtime WS origin check reads this.
ALLOWED_WS_ORIGINS = build_ws_origins()

# Hosts considered loopback — empty-Origin connections are allowed only from
# these addresses so non-browser local processes on non-loopback interfaces
# cannot bypass the origin check (fixes #3845).
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


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
        """
        # Check Origin header for security (CORS does not apply to WebSocket upgrades).
        origin = websocket.headers.get("origin", "").lower()
        if origin:
            # Non-empty Origin: must be in the allowlist (fixes #2413).
            if origin not in ALLOWED_WS_ORIGINS:
                logger.warning(f"WebSocket connection rejected: untrusted origin {origin!r}")
                await websocket.close(code=1008)  # Policy Violation
                return
        else:
            # Empty Origin: allow only from loopback so non-browser processes
            # on non-loopback interfaces cannot bypass the check (fixes #3845).
            client_host = (websocket.client.host if websocket.client else "").lower()
            if client_host not in _LOOPBACK_HOSTS:
                logger.warning(
                    f"WebSocket connection rejected: empty Origin from non-loopback host {client_host!r}"
                )
                await websocket.close(code=1008)  # Policy Violation
                return

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

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcast message to all connected clients.

        Automatically removes stale connections that fail to receive messages.

        Args:
            message: Dictionary message to broadcast (will be JSON encoded)
        """
        stale_connections: list[WebSocket] = []

        async with self._lock:
            connections_snapshot = list(self.active_connections)

        message_json = json.dumps(message)

        for connection in connections_snapshot:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                stale_connections.append(connection)
                logger.debug(f"Marking stale connection for removal: {e}")

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
