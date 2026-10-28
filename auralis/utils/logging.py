"""
Auralis Logging System
~~~~~~~~~~~~~~~~~~~~~~

Logging and debug utilities

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Refactored from Matchering 2.0 by Sergree and contributors
"""

import logging as _stdlib_logging
import traceback as _traceback
from collections.abc import Callable
from types import TracebackType

# Control characters that must not reach a log line verbatim: C0 range
# (0x00-0x1F) except tab, plus DEL (0x7F) and the C1 range (0x80-0x9F).
# Newlines/carriage returns here let attacker-controlled metadata forge log
# lines; ESC (0x1B) and friends can corrupt a terminal log viewer (#4363).
_LOG_UNSAFE_CHARS = frozenset(
    chr(c) for c in range(0x00, 0x20) if c != 0x09
) | {chr(0x7F)} | frozenset(chr(c) for c in range(0x80, 0xA0))


def sanitize_log_value(value: object, max_length: int = 500) -> str:
    """Make an untrusted value safe to interpolate into a single log line.

    Track/tag metadata and client-supplied filenames can contain ``\\r\\n``
    (forging extra log lines) or terminal control sequences (corrupting a log
    viewer). This coerces ``value`` to ``str``, escapes every unsafe control
    character as its ``\\xNN`` form, and truncates to ``max_length`` so a huge
    tag can't flood the log. The result is always a single printable line.

    Args:
        value: Any value (coerced via ``str``); typically metadata/filename.
        max_length: Maximum length before truncation (appends an ellipsis).

    Returns:
        A single-line, control-character-free string safe for logging.
    """
    text = str(value)
    if len(text) > max_length:
        text = text[:max_length] + "…"
    if not any(ch in _LOG_UNSAFE_CHARS for ch in text):
        return text  # fast path: nothing to escape
    return "".join(
        f"\\x{ord(ch):02x}" if ch in _LOG_UNSAFE_CHARS else ch for ch in text
    )


class Code:
    """Log message codes"""
    INFO_LOADING = "Loading audio files..."
    INFO_EXPORTING = "Exporting results..."
    INFO_COMPLETED = "Processing completed successfully"
    ERROR_VALIDATION = "Validation error"
    ERROR_LOADING = "Error loading audio file"
    ERROR_INVALID_AUDIO = "Invalid audio file format"
    ERROR_FILE_NOT_FOUND = "File not found"
    ERROR_EMPTY_AUDIO = "Empty audio file"
    ERROR_INVALID_SAMPLE_RATE = "Invalid sample rate"
    ERROR_FFMPEG_NOT_FOUND = "FFmpeg not found"
    ERROR_FFMPEG_CONVERSION = "FFmpeg conversion error"
    ERROR_FFMPEG_TIMEOUT = "FFmpeg conversion timeout"
    ERROR_TRUNCATED_FILE = "Truncated audio file"
    WARNING_TRUNCATED_FILE = "Audio file may be truncated"
    ERROR_EMPTY_FILE = "Empty file"
    ERROR_UNSUPPORTED_FORMAT = "Unsupported format"
    ERROR_CORRUPTED = "Corrupted or unsupported audio file"
    ERROR_NAN_DETECTED = "NaN or Inf values detected in audio"
    WARNING_NAN_DETECTED = "NaN or Inf values detected and repaired"


class ModuleError(Exception):
    """Custom exception for module errors.

    `path`, when given, carries the filesystem path involved in the failure
    as a structured attribute rather than interpolated into the message
    string. FFmpeg/ffprobe raise sites used to embed the absolute path (and,
    separately, raw subprocess stderr) directly into the exception's string
    form (#4806) — nothing currently forwards `str(exc)` to an HTTP/WS
    client, but a future "surface a more specific ModuleError message"
    change would have started doing exactly that. A caller that needs the
    path for its own DEBUG-level logging should read `.path`, not parse it
    back out of `str(exc)`.
    """
    def __init__(self, code: str, path: str | None = None) -> None:
        self.code = code
        self.path = path
        super().__init__(f"Module error: {code}")


# Global log handler. When none is installed the facade bridges to the stdlib
# "auralis" logger instead of discarding every event (#6156): no production code
# ever called set_log_handler, so the failure paths of the scanner, database,
# loaders and metadata backup were invisible in the persisted log.
_log_handler: Callable[[str], None] | None = None
_stdlib_logger = _stdlib_logging.getLogger("auralis")


def set_log_handler(handler: Callable[[str], None] | None) -> None:
    """Install a custom handler, or ``None`` to restore the stdlib bridge."""
    global _log_handler
    _log_handler = handler


def _emit(level: int, label: str, message: str) -> None:
    """Route one facade message to the custom handler, else the "auralis" logger."""
    text = sanitize_log_value(message)
    if _log_handler:
        _log_handler(f"{label}: {text}")
        return
    if _stdlib_logger.isEnabledFor(level):
        # stacklevel=3 attributes the record to the facade's caller, not to _emit.
        _stdlib_logger.log(level, "%s", text, stacklevel=3)


def debug(message: str) -> None:
    """Log a debug message"""
    _emit(_stdlib_logging.DEBUG, "DEBUG", message)


def info(message: str) -> None:
    """Log an info message"""
    _emit(_stdlib_logging.INFO, "INFO", message)


def warning(message: str) -> None:
    """Log a warning message"""
    _emit(_stdlib_logging.WARNING, "WARNING", message)


def error(message: str) -> None:
    """Log an error message"""
    _emit(_stdlib_logging.ERROR, "ERROR", message)


# #4828: the explicit sanitize_log_value() call sites from #4363 (4 files) left
# dozens of other sites across auralis/ and auralis-web/backend/ interpolating
# untrusted filenames/tags into log messages unsanitized — sanitize_log_value()
# was never a global hook, just a function every call site had to opt into.
#
# Rather than touching every site individually (an unbounded, easy-to-miss
# list), sanitization is applied centrally at the two places log messages
# actually get emitted:
#   - debug/info/warning/error above, for this module's own callers.
#   - the stdlib `logging` LogRecordFactory below, for the rest of the
#     codebase (mainly auralis-web/backend/, which uses
#     `logging.getLogger(__name__)` throughout rather than this module).
# Both are idempotent (sanitize_log_value's fast path is a no-op on text with
# no unsafe characters), so this is safe even where a call site already
# sanitizes explicitly.
_original_log_record_factory = _stdlib_logging.getLogRecordFactory()

# Args of these types pass through the LogRecordFactory untouched: their
# str()/repr() is control-character-free by construction, and %-formatting
# needs the object itself ("%d" % ("5",) raises TypeError). Everything else
# — Path, Exception, anything with a custom __str__ that can carry raw
# attacker-controlled text (#5393) — is str()-coerced and sanitized now,
# rather than left opaque for getMessage() to interpolate after
# sanitization has already run.
_ARG_PASSTHROUGH_TYPES = (int, float, complex, type(None), bytes, bytearray)


def _sanitized_log_arg(arg: object) -> object:
    """Sanitize one %-style logging arg, preserving numeric format specifiers."""
    if isinstance(arg, str):
        return sanitize_log_value(arg)
    if isinstance(arg, _ARG_PASSTHROUGH_TYPES):
        return arg
    return sanitize_log_value(arg)


def _sanitizing_log_record_factory(*args: object, **kwargs: object) -> _stdlib_logging.LogRecord:
    """LogRecordFactory wrapper that sanitizes a record's message/args in place.

    Covers %-style logging (``logger.info("...%s...", value)``) as well as
    pre-interpolated f-strings. Non-str args are sanitized too (#5393): a
    ``Path`` or ``Exception`` arg interpolates attacker-controlled text via
    getMessage()'s %-formatting, which runs AFTER this factory, so the object
    is str()-coerced and escaped here instead. Traceback text still bypasses
    this factory (it is formatted separately by the handler's Formatter) —
    ``SanitizingFormatter`` below covers that half.
    """
    record = _original_log_record_factory(*args, **kwargs)
    if isinstance(record.msg, str):
        record.msg = sanitize_log_value(record.msg)
    if isinstance(record.args, tuple):
        record.args = tuple(_sanitized_log_arg(arg) for arg in record.args)
    elif isinstance(record.args, dict):  # %(key)s style: sanitize the values
        record.args = {key: _sanitized_log_arg(value) for key, value in record.args.items()}
    return record


_stdlib_logging.setLogRecordFactory(_sanitizing_log_record_factory)


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
    through ``sanitize_log_value()``. Cause/context chains are rendered
    recursively, matching the stdlib's structure.
    """

    _CAUSE_DIVIDER = (
        "\nThe above exception was the direct cause of the following exception:\n\n"
    )
    _CONTEXT_DIVIDER = (
        "\nDuring handling of the above exception, another exception occurred:\n\n"
    )

    def formatException(
        self,
        exc_info: tuple[type[BaseException], BaseException, TracebackType | None]
        | tuple[None, None, None],
    ) -> str:
        return self._format_chain(exc_info[1], exc_info[2], set())

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
