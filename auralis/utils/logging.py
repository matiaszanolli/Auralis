"""
Auralis Logging System
~~~~~~~~~~~~~~~~~~~~~~

Logging and debug utilities

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""

from collections.abc import Callable

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
    """Custom exception for module errors"""
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Module error: {code}")


# Global log handler and level
_log_handler: Callable[[str], None] | None = None
_log_level: str = "INFO"


def set_log_handler(handler: Callable[[str], None] | None) -> None:
    """Set the global log handler function"""
    global _log_handler
    _log_handler = handler


def set_log_level(level: str) -> None:
    """Set the global log level"""
    global _log_level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    if level.upper() in valid_levels:
        _log_level = level.upper()


def get_log_level() -> str:
    """Get the current log level"""
    return _log_level


def debug(message: str) -> None:
    """Log a debug message"""
    if _log_handler:
        _log_handler(f"DEBUG: {message}")


def info(message: str) -> None:
    """Log an info message"""
    if _log_handler:
        _log_handler(f"INFO: {message}")


def warning(message: str) -> None:
    """Log a warning message"""
    if _log_handler:
        _log_handler(f"WARNING: {message}")


def error(message: str) -> None:
    """Log an error message"""
    if _log_handler:
        _log_handler(f"ERROR: {message}")


def debug_line() -> None:
    """Log a debug separator line"""
    if _log_handler:
        _log_handler("-" * 50)