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
import logging
import threading
from dataclasses import dataclass, field
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
    # Per-connection snapshot of the preset/intensity/enabled actually resolved
    # for THIS connection's current stream, keyed by ws_id (#4742). handle_seek
    # reads this instead of the process-global enhancement_settings dict, so a
    # second connection's play_enhanced can no longer retarget a first
    # connection's subsequent seeks. Defaulted so existing keyword
    # constructions (production and tests) keep working unchanged.
    active_stream_settings: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Cooperative-cancel signal for the enhanced/seek streaming paths (#4815).
    # `old_task.cancel()` cancels the asyncio coroutine promptly, but the
    # concurrent.futures.Future running the actual chunk DSP inside
    # STREAM_EXECUTOR is already running by the time that happens and does
    # NOT stop — .cancel() on a running future is a no-op. The streaming
    # entry point (stream_enhanced.py/stream_seek.py) creates one
    # threading.Event per active stream, keyed by ws_id, and passes it into
    # ChunkedAudioProcessor; _cancel_prior_task/handle_stop set() it before
    # cancelling the task so the in-flight DSP call can check it and bail
    # out early instead of running to completion unreferenced. Same pattern
    # ProcessingEngine._cancel_events already uses for FFmpeg decode.
    chunk_cancel_events: dict[str, threading.Event] = field(default_factory=dict)


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
    # Broadcast manager, so handlers can emit connection-independent events
    # (mastering_recommendation, #4542). Optional/defaulted so existing
    # constructions — including those in tests — keep working.
    broadcast_manager: Any = None


async def await_cancelled_task(task: "asyncio.Task[None]", logger: logging.Logger) -> None:
    """Await a task the caller has already called ``.cancel()`` on, swallowing
    the OLD task's own teardown exceptions (including its own CancelledError)
    — but re-raising if the CURRENT task is itself being cancelled (#4809).

    ``except (asyncio.CancelledError, Exception): pass`` around a bare
    ``await old_task`` cannot tell "the awaited task finished handling its
    own cancellation" from "something (shutdown, client disconnect) is
    cancelling the caller too" — both surface as ``CancelledError`` at this
    await point. Swallowing the latter lets the receive loop run one more
    iteration after being told to stop. ``Task.cancelling()`` (3.11+)
    distinguishes them: it is nonzero only when a cancellation request
    targets the current task.
    """
    try:
        await task
    except asyncio.CancelledError:
        current = asyncio.current_task()
        if current is not None and current.cancelling():
            raise
    except Exception:
        logger.debug("Prior task raised while awaiting its cancellation", exc_info=True)
