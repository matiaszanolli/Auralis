#!/usr/bin/env python3

"""
Safe error-message mapping for the processing engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Maps exceptions raised while loading, processing, or saving audio to a small
set of user-safe category strings. Extracted from processing_engine.py
(#4250 follow-up: the mechanical pool/worker/process_job split landed in
3b01a65e, but the engine module itself kept growing past the 300-line
convention through unrelated bugfixes — this is the next safe slice out of
it). The mapping tables and match order are unchanged; re-exported from
processing_engine.py so `from core.processing_engine import
_safe_error_message` keeps working for routers/tests that import it from
there.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from auralis.utils.logging import Code, ModuleError
from core.encoding import WAVEncoderError

__all__ = ["_safe_error_message"]

# Maps exception types to user-safe messages.  Order matters: first
# match wins, so put specific types before broad ones.
_ERROR_CATEGORIES: list[tuple[type[BaseException], str]] = [
    # #5147: WAVEncoderError used to be appended here inside a
    # `try: from encoding.wav_encoder import ... except ImportError: pass`,
    # because that module was only importable when auralis-web/backend
    # happened to be on sys.path. Any environment where that failed silently
    # lost the mapping and reported encoder failures under the generic
    # message. It now comes from the core.encoding package, which is a normal
    # relative sibling and cannot fail to import, so it is stated inline.
    (WAVEncoderError, "Audio encoding failed"),
    (FileNotFoundError, "Audio file not found"),
    (PermissionError, "Permission denied accessing audio file"),
    (OSError, "Audio file could not be read"),
    (ValueError, "Invalid audio data or parameters"),
    (MemoryError, "Insufficient memory to process audio"),
]

# auralis.io.unified_loader (and its loaders/ siblings) raise ModuleError — a
# bare Exception subclass — for every load failure instead of a stdlib
# exception type, so it never matched _ERROR_CATEGORIES above and every load
# failure collapsed into the generic fallback (#4769). ModuleError.code is the
# formatted "<Code.* value>: <detail>" string, so match on its prefix rather
# than isinstance. Order matters: first match wins.
_MODULE_ERROR_CATEGORIES: list[tuple[str, str]] = [
    (Code.ERROR_FILE_NOT_FOUND, "Audio file not found"),
    (Code.ERROR_EMPTY_FILE, "Audio file is empty"),
    (Code.ERROR_EMPTY_AUDIO, "Audio file contains no audio data"),
    (Code.ERROR_UNSUPPORTED_FORMAT, "Unsupported audio format"),
    (Code.ERROR_INVALID_SAMPLE_RATE, "Invalid audio sample rate"),
    (Code.ERROR_INVALID_AUDIO, "Invalid or corrupted audio data"),
    (Code.ERROR_TRUNCATED_FILE, "Audio file appears to be truncated or incomplete"),
    (Code.ERROR_CORRUPTED, "Audio file is corrupted or unsupported"),
    (Code.ERROR_FFMPEG_NOT_FOUND, "Audio decoder unavailable on server"),
    (Code.ERROR_FFMPEG_TIMEOUT, "Audio conversion timed out"),
    (Code.ERROR_FFMPEG_CONVERSION, "Audio file could not be converted"),
    (Code.ERROR_LOADING, "Audio file could not be loaded"),
    (Code.ERROR_VALIDATION, "Audio validation failed"),
    (Code.ERROR_NAN_DETECTED, "Audio file contains invalid sample values"),
]


def _safe_error_message(exc: Exception) -> str:
    """Return a user-safe error category for *exc*.

    The raw exception is intentionally NOT included — callers must log
    it separately so internal paths / library internals stay server-side.
    This also applies to ModuleError.code, which can embed absolute paths
    or raw FFmpeg stderr; only the mapped category string is ever returned.
    """
    if isinstance(exc, ModuleError):
        code = getattr(exc, "code", "") or ""
        for prefix, message in _MODULE_ERROR_CATEGORIES:
            if code.startswith(prefix):
                return message
        return "Audio file could not be processed"
    for exc_type, message in _ERROR_CATEGORIES:
        if isinstance(exc, exc_type):
            return message
    return "An unexpected error occurred during processing"
