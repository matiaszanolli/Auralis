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
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PathValidationError(Exception):
    """Raised when path validation fails."""

    def log_text(self) -> str:
        """The message to persist at WARNING; containment/traversal messages are already path-free."""
        return str(self)


class PathMissingError(PathValidationError):
    """A path that is well-formed and contained but absent on disk (#5080).

    Kept apart from "escapes the allowed directories" so a caller can tell a deleted, moved or unplugged-drive
    track (offer relocate/remove) from a malformed request. Subclassing ``PathValidationError`` keeps every
    existing ``except PathValidationError`` handler working; a caller that wants the distinction catches this first.
    """

    def log_text(self) -> str:
        """The absolute path is the commonest thing users paste into public issues: log the file name (#6189)."""
        reason, _, path = str(self).rpartition(": ")
        return f"{reason}: {Path(path).name}" if reason else Path(path).name


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
                e.log_text(),
            )
            logger.debug("Path validation rejection (full): %s", e)
            raise
    return wrapper
