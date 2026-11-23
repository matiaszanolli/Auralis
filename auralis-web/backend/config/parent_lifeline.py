"""
Stdin lifeline: the packaged backend exits when the Electron process that started it is gone (#6720)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Electron stops the backend from ``before-quit``, which only runs inside a live
main process. A crash, a SIGKILL (Force Quit, the OOM killer) or a debugger
stop skipped it, and the backend (detached on POSIX; on Windows a child is
never terminated with its parent either) kept 127.0.0.1:8765 and the library
DB open. Every later launch then failed to bind the port, and nothing reclaimed
it, since the port sweep was removed on purpose (#6518).

Electron spawns the backend with a stdin pipe it never writes to or closes, and
sets ``AURALIS_STDIN_LIFELINE=1``. The OS closes that pipe when the Electron
process exits, by any means and on every platform, so end-of-file on stdin means
the parent is gone. The backend then raises the signal uvicorn already handles,
so the lifespan shutdown (WAL checkpoint included) runs as on a normal quit. A
hard exit follows if that shutdown overruns its budgets.

Only the opt-in variable enables it: a backend started from a terminal, by
``dev.js`` or by tests must never treat its stdin as a lifeline.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import os
import signal
import sys
import threading
from collections.abc import Callable
from typing import BinaryIO

from config.limits import SHUTDOWN_STEP_TIMEOUT_S, SHUTDOWN_TOTAL_TIMEOUT_S

logger = logging.getLogger(__name__)

LIFELINE_ENV = "AURALIS_STDIN_LIFELINE"

# uvicorn's graceful drain (timeout_graceful_shutdown = one step budget), then the lifespan
# teardown (its own total deadline), then one more step for the checkpoint and pool shutdown.
HARD_EXIT_AFTER_S = SHUTDOWN_TOTAL_TIMEOUT_S + 2 * SHUTDOWN_STEP_TIMEOUT_S


def _request_graceful_exit() -> None:
    """Raise the signal uvicorn handles (SIGINT on Windows, where SIGTERM cannot be raised to a
    handler), and arm a hard exit in case the shutdown never finishes."""
    timer = threading.Timer(HARD_EXIT_AFTER_S, os._exit, args=(1,))
    timer.daemon = True
    timer.start()
    signal.raise_signal(signal.SIGINT if sys.platform == "win32" else signal.SIGTERM)


def watch_parent_stream(stream: BinaryIO, on_parent_gone: Callable[[], None]) -> None:
    """Block until ``stream`` reaches end of file, then call ``on_parent_gone``.

    Anything written is discarded: Electron writes nothing. A broken pipe is how
    Windows reports the parent's end of a pipe closing, so it counts as end of
    file. Any other read error is not proof the parent is gone: it is logged,
    and the watch stops without shutting a healthy backend down.
    """
    try:
        while stream.read(4096):
            pass
    except BrokenPipeError:
        pass
    except (OSError, ValueError) as exc:
        logger.warning(f"Parent lifeline stopped watching stdin: {type(exc).__name__}: {exc}")
        return
    logger.warning("The process that started the backend is gone (its stdin pipe closed); shutting down")
    on_parent_gone()


def start_parent_lifeline(
    stream: BinaryIO | None = None,
    on_parent_gone: Callable[[], None] = _request_graceful_exit,
) -> threading.Thread | None:
    """Watch stdin on a daemon thread when ``AURALIS_STDIN_LIFELINE=1``; return the thread, or None."""
    if os.environ.get(LIFELINE_ENV) != "1":
        return None
    if stream is None:
        stdin = sys.stdin
        if stdin is None or not hasattr(stdin, "buffer"):
            logger.warning(f"{LIFELINE_ENV} is set but the backend has no stdin to watch")
            return None
        stream = stdin.buffer
    thread = threading.Thread(
        target=watch_parent_stream, args=(stream, on_parent_gone), name="parent-lifeline", daemon=True
    )
    thread.start()
    logger.info("Watching stdin: the backend exits when the app that started it does")
    return thread
