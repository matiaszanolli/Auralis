"""
Auralis Logging System
~~~~~~~~~~~~~~~~~~~~~~

Logging and debug utilities

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Refactored from Matchering 2.0 by Sergree and contributors
"""

import logging as _stdlib_logging
import os as _os
from collections.abc import Callable

# Control characters that must not reach a log line verbatim: C0 range
# (0x00-0x1F) except tab, plus DEL (0x7F) and the C1 range (0x80-0x9F).
# Newlines/carriage returns here let attacker-controlled metadata forge log
# lines; ESC (0x1B) and friends can corrupt a terminal log viewer (#4363).
_LOG_UNSAFE_CHARS = frozenset(
    chr(c) for c in range(0x00, 0x20) if c != 0x09
) | {chr(0x7F)} | frozenset(chr(c) for c in range(0x80, 0xA0))


# The user's home directory carries their OS account name and the install layout; every path under it
# reads as "~/..." in persisted logs (#6189). Resolved once: a log call must not hit the filesystem.
try:
    _HOME_PREFIX = _os.path.expanduser("~")
except Exception:  # noqa: BLE001 - no resolvable home (a bare service account): nothing to redact
    _HOME_PREFIX = ""
if len(_HOME_PREFIX) < 2:  # "" or "/": redacting would mangle every path
    _HOME_PREFIX = ""


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
    if _HOME_PREFIX and _HOME_PREFIX in text:
        text = text.replace(_HOME_PREFIX, "~")
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
        # A template with args is escaped, never truncated: a cut-off %s left args unconverted,
        # so getMessage() raised and the record was lost (#6544). The args keep their own cap.
        record.msg = sanitize_log_value(record.msg, len(record.msg) if record.args else 500)
    if isinstance(record.args, tuple):
        record.args = tuple(_sanitized_log_arg(arg) for arg in record.args)
    elif isinstance(record.args, dict):  # %(key)s style: sanitize the values
        record.args = {key: _sanitized_log_arg(value) for key, value in record.args.items()}
    return record


_stdlib_logging.setLogRecordFactory(_sanitizing_log_record_factory)


# The traceback formatter lives in log_formatter.py (#6534); re-exported so callers keep importing it from here.
from .log_formatter import SanitizingFormatter, install_sanitizing_formatter  # noqa: E402, F401
