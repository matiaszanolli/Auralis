"""
FFmpeg subprocess supervision (split from ffmpeg_loader.py, #5835): the shared
subprocess text/timeouts, stderr redaction, and the cancellable runner.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import subprocess
import threading
import time
from typing import Any

# Every ffmpeg/ffprobe capture decodes with these. Bare ``text=True`` uses the
# locale codec in strict mode, and FFmpeg echoes input metadata and the input
# filename into stderr verbatim: an ID3v1 tag (always Latin-1) or a filename
# with a raw non-UTF-8 byte made ``subprocess.run`` raise UnicodeDecodeError on
# a perfectly decodable file (#5555). ``errors='replace'`` keeps the diagnostic
# readable and the process result intact.
SUBPROCESS_TEXT_KWARGS: dict[str, Any] = {'text': True, 'encoding': 'utf-8', 'errors': 'replace'}

# Subprocess time budgets, in seconds. The ffprobe one is shared with
# unified_loader.get_audio_info: two hand-written copies of that probe had
# already drifted once (#5326) and their timeouts were still separate literals
# (#5798).
FFPROBE_TIMEOUT_S = 30           # one ffprobe call describing one file
FFMPEG_VERSION_CHECK_TIMEOUT_S = 10   # `ffmpeg -version` / `ffprobe -version` availability probes
FFMPEG_DECODE_TIMEOUT_S = 300    # one whole ffmpeg decode (5 minutes, regardless of file length)
FFMPEG_TERMINATE_GRACE_S = 5     # terminate() -> kill() grace for a cancelled child

_STDERR_TAIL_MAX_CHARS = 200


def redact_subprocess_output(
    raw: str | None, max_chars: int = _STDERR_TAIL_MAX_CHARS, known_path: str | None = None
) -> str:
    """Bound a subprocess's raw stderr before it reaches a ``ModuleError`` message.

    FFmpeg/ffprobe stderr always opens with a multi-line build-config banner,
    and the actual failure reason is reliably the last non-empty line — so
    keep only that, bounded to *max_chars*. That last line commonly reads
    ``<input>: <reason>`` (e.g. ``/home/user/Music/track.mp3: Invalid data
    found when processing input``), i.e. FFmpeg's own error format puts the
    echoed input path on the SAME line as the reason, not just in the banner
    above (#4806) — a plain last-line truncation still leaks it. Pass
    *known_path* (the exact string handed to FFmpeg/ffprobe as the input) to
    strip it from the tail too. Shared by both the ffmpeg conversion failure
    and the ffprobe non-zero-exit call sites.
    """
    text = (raw or "").strip()
    if not text:
        return "(no output)"
    if known_path:
        text = text.replace(known_path, "<file>")
    tail = text.splitlines()[-1].strip() or text.splitlines()[-1]
    if len(tail) > max_chars:
        tail = "…" + tail[-max_chars:]
    return tail


def _terminate_process(proc: "subprocess.Popen[str]") -> None:
    """Terminate an FFmpeg child promptly: SIGTERM, escalate to SIGKILL.

    Best-effort — the child is going away regardless, so any error while
    signalling it is swallowed.
    """
    try:
        proc.terminate()
        try:
            proc.wait(timeout=FFMPEG_TERMINATE_GRACE_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=FFMPEG_TERMINATE_GRACE_S)
    except Exception:
        pass


def _run_ffmpeg_cancellable(
    cmd: list[str],
    timeout: float,
    cancel_event: "threading.Event | None",
) -> "subprocess.CompletedProcess[str]":
    """Run an FFmpeg command, honouring a cooperative cancellation token.

    With no ``cancel_event`` this is a plain blocking ``subprocess.run`` —
    byte-for-byte the previous behaviour, so library-scan and other non-job
    callers are unaffected.

    With a ``cancel_event``, FFmpeg runs under ``Popen`` and is polled so that a
    ``cancel_event.set()`` from another thread (``ProcessingEngine.cancel_job``)
    terminates the child within ~100 ms instead of parking a worker thread and a
    CPU core for up to ``timeout`` seconds (#4496). On cancel the child is
    terminated and ``asyncio.CancelledError`` is raised so the abort surfaces as
    a clean cancellation rather than a spurious decode failure.
    """
    if cancel_event is None:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, **SUBPROCESS_TEXT_KWARGS)

    if cancel_event.is_set():
        raise asyncio.CancelledError()

    # FFmpeg writes the decoded WAV to a file (not stdout), so stdout stays
    # empty and stderr carries only modest progress text — the pipe buffers
    # never fill, so repeated poll-timeout communicate() calls cannot deadlock.
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **SUBPROCESS_TEXT_KWARGS
    )
    start = time.monotonic()
    poll_interval = 0.1
    while True:
        try:
            stdout, stderr = proc.communicate(timeout=poll_interval)
            return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            if cancel_event.is_set():
                _terminate_process(proc)
                raise asyncio.CancelledError()
            if time.monotonic() - start > timeout:
                _terminate_process(proc)
                raise  # -> ModuleError(ERROR_FFMPEG_TIMEOUT) in the caller
