"""
Regression: cancelling a job must stop the in-flight FFmpeg subprocess (#4496)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``cancel_job()`` previously only called ``task.cancel()``, which cannot
interrupt the blocking ``subprocess.run`` running inside a ``to_thread``
worker — the FFmpeg child and its thread-pool slot kept running for up to the
300 s timeout after "cancellation".

``load_with_ffmpeg`` now runs FFmpeg under ``Popen`` and polls a cooperative
``threading.Event`` cancel token; setting it terminates the child within
~100 ms and raises ``asyncio.CancelledError`` (a clean cancellation, not a
decode failure).

These tests drive the real ``_run_ffmpeg_cancellable`` with a portable
long-running command (``sleep``) so they do not depend on FFmpeg being present.
"""

import asyncio
import subprocess
import threading
import time

import pytest

from auralis.io.loaders import ffmpeg_loader
from auralis.io.loaders.ffmpeg_loader import _run_ffmpeg_cancellable


class TestRunFfmpegCancellable:
    def test_no_cancel_event_behaves_like_subprocess_run(self):
        """With cancel_event=None the runner is a plain blocking run."""
        result = _run_ffmpeg_cancellable(["true"], timeout=10, cancel_event=None)
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 0

    def test_preset_cancel_event_raises_immediately(self):
        """An already-set token aborts before spawning the child."""
        event = threading.Event()
        event.set()
        with pytest.raises(asyncio.CancelledError):
            _run_ffmpeg_cancellable(["sleep", "30"], timeout=30, cancel_event=event)

    def test_cancel_mid_run_terminates_promptly(self, monkeypatch):
        """Setting the token mid-run terminates the child and raises promptly,
        not after the full timeout — and the terminate path is invoked."""
        terminated: list[bool] = []
        real_terminate = ffmpeg_loader._terminate_process

        def _spy_terminate(proc):
            terminated.append(True)
            real_terminate(proc)

        monkeypatch.setattr(ffmpeg_loader, "_terminate_process", _spy_terminate)

        event = threading.Event()
        # Fire the cancel shortly after the child starts.
        timer = threading.Timer(0.3, event.set)
        timer.start()

        start = time.monotonic()
        try:
            with pytest.raises(asyncio.CancelledError):
                _run_ffmpeg_cancellable(["sleep", "30"], timeout=30, cancel_event=event)
        finally:
            timer.cancel()
        elapsed = time.monotonic() - start

        assert elapsed < 10, f"cancel took {elapsed:.1f}s — child was not stopped promptly"
        assert terminated, "the FFmpeg terminate path was not invoked on cancel"

    def test_normal_completion_returns_result(self):
        """A short command that finishes before any cancel returns normally
        even when a (never-set) token is supplied."""
        event = threading.Event()
        result = _run_ffmpeg_cancellable(["true"], timeout=10, cancel_event=event)
        assert result.returncode == 0
