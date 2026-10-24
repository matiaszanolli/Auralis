"""
Path Validation Errors
~~~~~~~~~~~~~~~~~~~~~~

PathValidationError / PathMissingError and the @_logs_rejections decorator,
split from path_security.py (#6271).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import functools
import logging
from collections.abc import Callable
from typing import Any
from pathlib import Path

logger = logging.getLogger(__name__)


class PathValidationError(Exception):
    """Raised when path validation fails."""
    pass


class PathMissingError(PathValidationError):
    """Raised when a path is well-formed and contained, but absent on disk.

    #5080: ``validate_file_path()`` used to report "this path escapes the
    allowed directories" and "this file no longer exists" with the same
    exception type, so every caller that mapped ``PathValidationError`` to
    HTTP 400 answered 400 for a track whose file had been deleted, moved or
    lives on an unplugged drive — the most common desktop failure mode for a
    file-backed library, and the one case a client genuinely needs to tell
    apart (offer relocate/remove vs. report a malformed request).

    Subclassing ``PathValidationError`` keeps every existing
    ``except PathValidationError`` handler working unchanged; a caller that
    wants the distinction catches this first. Raised ONLY by the
    existence/is-a-file checks — a containment, traversal, empty-path or
    unreadable-path rejection stays a plain ``PathValidationError``.
    """
    pass


def _logs_rejections(fn: Callable[..., Path]) -> Callable[..., Path]:
    """Emit exactly one warning whenever the wrapped validator rejects a path.

    #4925: rejections used to be logged only by whichever caller remembered
    to. Six call sites did, six did not — so a traversal probe against, say,
    ``/api/settings/scan-folder`` left no trace at all, just a 400 to the
    client, and repeated probing could not be noticed after the fact. Only the
    SUCCESS path was logged here, at debug.

    Wrapping rather than editing each ``raise`` site keeps the original
    exception and its traceback untouched (bare ``raise``), and means a
    validator that grows a new rejection branch is covered automatically
    instead of relying on someone remembering this rule.

    The corollary: callers must NOT log their own warning or the line doubles.
    Callers that know something the validator cannot — which track, which
    request parameter — pass ``context`` instead, so the single line still
    carries it.

    Typed as ``Callable[..., Path]`` deliberately: ``context`` is injected by
    the wrapper and is not part of the wrapped function's own signature, so a
    precise ``ParamSpec`` would reject every caller that passes it.
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, context: str | None = None, **kwargs: Any) -> Path:
        try:
            return fn(*args, **kwargs)
        except PathValidationError as e:
            logger.warning(
                "Path validation rejected%s: %s",
                f" ({context})" if context else "",
                e,
            )
            raise
    return wrapper
