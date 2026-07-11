"""
WebSocket Handler Context
~~~~~~~~~~~~~~~~~~~~~~~~~

Shared state/dependency bundles passed into the per-message-type handlers.

`StreamState` wraps the module-level mutable dicts/lock that live in
routers/system.py (deliberately NOT redefined here — the caller constructs
this from its own module globals so identity is preserved across the
system_module._active_streaming_tasks_lock-style direct references used by
tests). `WSDeps` bundles the injected factories plus the three streaming
coroutines (stream_audio/stream_normal/stream_from_position) so handlers can
call them without importing routers.system (which would import this package,
creating a cycle) — passing them by reference also preserves
patch.object(system_module, "stream_audio", ...) patchability, since the
caller reads the (possibly patched) module global once per connection.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable


@dataclass
class StreamState:
    """Per-process streaming state, keyed by ws_id. Shared across all connections."""

    active_tasks: dict[str, asyncio.Task[None]]
    active_tasks_lock: asyncio.Lock
    active_track_ids: dict[str, int]
    pause_events: dict[str, asyncio.Event]
    flow_events: dict[str, asyncio.Event]


@dataclass
class WSDeps:
    """Injected factories and streaming coroutines for one connection."""

    get_repository_factory: Callable[..., Any] | None
    get_enhancement_settings: Callable[[], dict[str, Any]] | None
    get_cache_manager: Callable[[], Any] | None
    get_processing_engine: Callable[..., Any]
    stream_audio: Callable[..., Any]
    stream_normal: Callable[..., Any]
    stream_from_position: Callable[..., Any]
