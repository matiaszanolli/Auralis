"""The packaged backend exits when the Electron process that started it is gone (#6720).

A crashed or SIGKILLed Electron never runs ``before-quit``, so the backend it
spawned kept 127.0.0.1:8765 and the library DB open, and every later launch
failed to bind the port. Electron now gives the backend a stdin pipe it never
writes to; the OS closes it when the parent exits by any means, and the backend
shuts down through uvicorn's normal path on end-of-file.
"""

import io
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(BACKEND))

from config import parent_lifeline  # noqa: E402
from config.parent_lifeline import LIFELINE_ENV, start_parent_lifeline, watch_parent_stream  # noqa: E402


def test_nothing_is_watched_unless_the_spawner_opts_in(monkeypatch):
    monkeypatch.delenv(LIFELINE_ENV, raising=False)
    assert start_parent_lifeline(stream=io.BytesIO(b""), on_parent_gone=lambda: None) is None


def test_end_of_file_on_the_pipe_means_the_parent_is_gone(monkeypatch):
    monkeypatch.setenv(LIFELINE_ENV, "1")
    read_fd, write_fd = os.pipe()
    gone = threading.Event()

    thread = start_parent_lifeline(stream=os.fdopen(read_fd, "rb", buffering=0), on_parent_gone=gone.set)
    assert thread is not None
    os.write(write_fd, b"ignored")
    assert not gone.wait(0.3), "data on the pipe is not the parent going away"

    os.close(write_fd)
    assert gone.wait(5)
    thread.join(5)


class _Raises(io.RawIOBase):
    def __init__(self, exc):
        self._exc = exc

    def read(self, size=-1):
        raise self._exc


def test_a_broken_pipe_counts_as_the_parent_going_away():
    gone = threading.Event()
    watch_parent_stream(_Raises(BrokenPipeError()), gone.set)
    assert gone.is_set()


def test_any_other_read_error_stops_watching_without_a_shutdown():
    gone = threading.Event()
    watch_parent_stream(_Raises(OSError(5, "Input/output error")), gone.set)
    assert not gone.is_set()


def test_the_hard_exit_outlasts_every_graceful_budget():
    from config.limits import SHUTDOWN_STEP_TIMEOUT_S, SHUTDOWN_TOTAL_TIMEOUT_S

    assert parent_lifeline.HARD_EXIT_AFTER_S > SHUTDOWN_TOTAL_TIMEOUT_S + SHUTDOWN_STEP_TIMEOUT_S


_APP = textwrap.dedent('''
    import sys
    from contextlib import asynccontextmanager
    sys.path.insert(0, {backend!r})
    import uvicorn
    from fastapi import FastAPI
    from config.parent_lifeline import start_parent_lifeline

    @asynccontextmanager
    async def lifespan(app):
        start_parent_lifeline()
        open({ready!r}, "w").close()
        yield
        open({shutdown!r}, "w").close()   # the lifespan shutdown ran: a graceful exit

    uvicorn.run(FastAPI(lifespan=lifespan), host="127.0.0.1", port=0, log_level="warning")
''')

# Plays Electron: spawns the app with a stdin pipe it never writes to, then waits to be killed.
_LAUNCHER = textwrap.dedent('''
    import os, subprocess, sys, time
    child = subprocess.Popen([sys.executable, {app!r}], stdin=subprocess.PIPE,
                             env={{**os.environ, "AURALIS_STDIN_LIFELINE": "1"}})
    print(child.pid, flush=True)
    time.sleep(120)
''')


def _wait_for(predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie still answers kill(0); its parent (init, after the launcher's death) reaps it.
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split(")")[-1].split()[0] != "Z"
    except FileNotFoundError:
        return True


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL and /proc are POSIX")
def test_sigkilling_the_spawner_shuts_the_server_down_gracefully(tmp_path):
    ready, shutdown = tmp_path / "ready", tmp_path / "shutdown"
    app = tmp_path / "app.py"
    app.write_text(_APP.format(backend=str(BACKEND), ready=str(ready), shutdown=str(shutdown)))
    launcher_src = tmp_path / "launcher.py"
    launcher_src.write_text(_LAUNCHER.format(app=str(app)))

    launcher = subprocess.Popen([sys.executable, str(launcher_src)], stdout=subprocess.PIPE, text=True)
    assert launcher.stdout is not None
    server_pid = None
    try:
        server_pid = int(launcher.stdout.readline())
        assert _wait_for(ready.exists, 30), "the server never started"

        launcher.send_signal(signal.SIGKILL)  # no cleanup of any kind, like a crashed Electron
        launcher.wait(10)

        assert _wait_for(shutdown.exists, 30), "the lifespan shutdown never ran"
        assert _wait_for(lambda: not _alive(server_pid), 30), "the server outlived its spawner"
    finally:
        launcher.kill()
        if server_pid is not None and _alive(server_pid):
            os.kill(server_pid, signal.SIGKILL)
