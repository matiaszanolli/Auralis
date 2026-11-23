"""
Sanitizing Traceback Formatter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``logging.Formatter`` that renders ``exc_info`` without letting attacker-controlled text
(paths, tags, exception messages) forge log lines (#5393, #6161), split out of
``auralis/utils/logging.py`` (#6534); that module re-exports both names.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging as _stdlib_logging
import sys as _sys
import threading as _threading
import traceback as _traceback
from types import TracebackType

from .logging import sanitize_log_value


class SanitizingFormatter(_stdlib_logging.Formatter):
    """Formatter that sanitizes attacker-controlled traceback text (#5393).

    ``exc_info`` / ``logger.exception()`` output never passes through
    getMessage() or the sanitizing LogRecordFactory above — the Formatter
    renders it via the traceback module, whose final ``{Type}: {message}``
    line is exactly ``str(exc)``. A loader exception embedding a crafted
    path could therefore reach the persisted log with its CR/LFs intact.

    A post-render escape cannot fix this: by the time the text is split
    into lines, an embedded ``\\n`` has already become a line boundary. So
    the traceback is rebuilt from the stdlib's own frame rendering
    (``traceback.format_tb``, structural, not attacker-controlled) while
    the exception summary line — the only attacker-controlled part — goes
    through ``sanitize_log_value()``. Cause/context chains and exception-group
    members (#6534) are rendered recursively, matching the stdlib's structure.
    """

    _CAUSE_DIVIDER = (
        "\nThe above exception was the direct cause of the following exception:\n\n"
    )
    _CONTEXT_DIVIDER = (
        "\nDuring handling of the above exception, another exception occurred:\n\n"
    )

    def format(self, record: _stdlib_logging.LogRecord) -> str:
        # logging caches the first handler's traceback text on the record and every later handler
        # reuses it: a plain Formatter running first would hand us its unsanitized rendering (#6540).
        # Rendering ours afterwards also leaves the sanitized text for any handler after us.
        record.exc_text = None
        return super().format(record)

    def formatException(
        self,
        ei: tuple[type[BaseException], BaseException, TracebackType | None]
        | tuple[None, None, None],
    ) -> str:
        return self._format_chain(ei[1], ei[2], set())

    def _format_chain(
        self,
        exc: BaseException | None,
        tb: TracebackType | None,
        seen: set[int],
    ) -> str:
        if exc is None or id(exc) in seen:
            return ""
        seen.add(id(exc))
        parts: list[str] = []
        if exc.__cause__ is not None:
            parts.append(self._format_chain(exc.__cause__, exc.__cause__.__traceback__, seen))
            parts.append(self._CAUSE_DIVIDER)
        elif exc.__context__ is not None and not exc.__suppress_context__:
            parts.append(self._format_chain(exc.__context__, exc.__context__.__traceback__, seen))
            parts.append(self._CONTEXT_DIVIDER)
        parts.append("Traceback (most recent call last):\n")
        # Frames are built field by field: sanitizing a whole format_tb() entry
        # escaped its own structural newlines, collapsing every traceback onto
        # one line (#6161). The newlines below are ours; every value that could
        # carry one (a path, a function name, a source line) is escaped first.
        for frame in _traceback.extract_tb(tb):
            parts.append(
                f'  File "{sanitize_log_value(frame.filename)}", line {frame.lineno}, '
                f"in {sanitize_log_value(frame.name)}\n"
            )
            if frame.line:
                parts.append(f"    {sanitize_log_value(frame.line)}\n")
        # The one attacker-controlled line: fully sanitized (including any
        # embedded \r\n) before it is ever joined into the output.
        parts.append(sanitize_log_value(f"{type(exc).__name__}: {exc}") + "\n")
        if isinstance(exc, BaseExceptionGroup):
            parts.append(self._format_group_members(exc, seen))
        return "".join(parts)

    def _format_group_members(self, group: BaseExceptionGroup[BaseException], seen: set[int]) -> str:
        """Each sub-exception of a group, numbered and indented as the stdlib does (#6534).

        Its leaves live in ``.exceptions``, not the cause/context chain, so a TaskGroup failure
        logged only ``ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)``.
        """
        parts: list[str] = []
        for number, member in enumerate(group.exceptions, 1):
            parts.append(f"  +---------------- {number} ----------------\n")
            rendered = self._format_chain(member, member.__traceback__, seen)
            parts.extend(f"    | {line}\n" for line in rendered.splitlines())
        parts.append("  +------------------------------------\n")
        return "".join(parts)


def install_sanitizing_formatter(
    logger: _stdlib_logging.Logger | None = None, fmt: str | None = None
) -> None:
    """Swap a SanitizingFormatter onto every handler of `logger` (root default).

    basicConfig() instantiates a plain Formatter internally and accepts no
    custom Formatter class, so this re-wraps the handlers it created. When
    `fmt` is omitted, each handler's existing format string is reused.
    Handlers created later still need setFormatter() themselves.
    """
    target = _stdlib_logging.getLogger() if logger is None else logger
    for handler in target.handlers:
        format_string = fmt if fmt is not None else getattr(handler.formatter, "_fmt", None)
        handler.setFormatter(SanitizingFormatter(format_string))


def route_uncaught_to_logging() -> None:
    """Send uncaught exceptions and warnings through logging, so they are sanitized too (#6540).

    The sanitizer is the record factory plus the formatter; anything printed to stderr directly
    reached the persisted log verbatim: the traceback of an uncaught exception in a bare thread
    (fingerprint workers, gapless prebuffer, resource monitor) or the main thread, and
    ``warnings.warn`` output, either of which can carry a tag or file name. Install before any
    worker thread starts. Ctrl-C and a thread's SystemExit keep their default handling.
    """
    log = _stdlib_logging.getLogger("auralis.uncaught")

    def _excepthook(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            _sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("Uncaught exception", exc_info=(exc_type, exc, tb))

    def _thread_excepthook(args: _threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit or args.exc_value is None:
            return
        name = args.thread.name if args.thread is not None else "?"
        log.critical("Uncaught exception in thread %s", name,
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    _sys.excepthook = _excepthook
    _threading.excepthook = _thread_excepthook
    _stdlib_logging.captureWarnings(True)
