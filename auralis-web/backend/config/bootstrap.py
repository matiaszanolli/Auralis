"""
Process bootstrap for main.py: log level + root logger, and the ``sys.path``
setup that makes ``auralis`` importable in each execution context (split from
main.py, #5834).

Import-order contract: main.py must call :func:`configure_logging` and
:func:`configure_sys_path` BEFORE importing anything that pulls in ``auralis``
(``config.app`` and friends), and this module must not import ``auralis``
itself at module level -- doing so would work in a dev venv (auralis is
pip-installed there) and break the PyInstaller-frozen case, where the parent
directory is only added to ``sys.path`` by :func:`configure_sys_path`.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Log level (#5065). Resolved ONCE by main.py and applied to both basicConfig
# and uvicorn.run()'s log_level.
#
# Passing a level to uvicorn alone cannot make `logger.debug` reachable:
# uvicorn's configure_logging() only calls setLevel() on its own
# "uvicorn.error"/"uvicorn.access"/"uvicorn.asgi" loggers, and its default
# LOGGING_CONFIG has no "root" entry, so the root logger every module logger
# here propagates to is left exactly as basicConfig left it. The basicConfig
# level is what actually gates DEBUG for the application; uvicorn's log_level
# only gates uvicorn's own lines. Both come from one value so they can't
# diverge (before this, uvicorn was pinned to "info" while --dev put the root
# logger at DEBUG).
#
# Default: DEBUG in dev mode, INFO otherwise. The non-dev default must stay
# INFO -- #4366/#4778 demoted absolute paths (which embed the OS username and
# the install layout) to DEBUG precisely so INFO output is safe to paste into a
# public bug report, and raising the packaged default would undo that.
# AURALIS_LOG_LEVEL is the explicit opt-in for a support session on a packaged
# build; it is deliberately separate from AURALIS_DEV_MODE, which also enables
# Swagger/ReDoc and widens the CORS/WebSocket origin allowlists (#4802) -- far
# too much to turn on just to read DEBUG lines.
_LOG_LEVELS: dict[str, int] = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
    # uvicorn's TRACE_LOG_LEVEL (below DEBUG); accepted by its log_level too.
    "trace": 5,
}


def early_dev_mode() -> bool:
    """Dev-mode flag for logging, read before the ``sys.path`` bootstrap.

    Duplicated rather than reused from config.app.is_dev_mode(): that import
    pulls in `auralis.version`, and this must run before configure_sys_path()
    adds the frozen/Electron auralis_parent to sys.path.
    """
    return "--dev" in sys.argv or os.environ.get("AURALIS_DEV_MODE", "").lower() in ("1", "true", "yes")


def resolve_log_level(dev_mode: bool, env: Mapping[str, str] | None = None) -> str:
    """Resolve the process-wide log level name (a valid uvicorn `log_level`).

    AURALIS_LOG_LEVEL wins when it names a known level; otherwise the default is
    "debug" in dev mode and "info" everywhere else. An unrecognized value falls
    back to that default instead of raising -- a typo in an environment variable
    must not stop the backend from starting.
    """
    environ = os.environ if env is None else env
    requested = environ.get("AURALIS_LOG_LEVEL", "").strip().lower()
    if requested in _LOG_LEVELS:
        return requested
    return "debug" if dev_mode else "info"


def configure_logging(dev_mode: bool) -> str:
    """Install the root logger handler (#4774) and return the level name.

    logging.basicConfig was removed once (#3537 / BE-NEW-79), then reinstated
    (#4774). Every module logger in this codebase has no handler of its own and
    propagates to the root logger; uvicorn's loggers never reach root (they
    configure only "uvicorn"/"uvicorn.access"/"uvicorn.error"). With no
    basicConfig, root has no handler either, so `logging.lastResort` (level
    WARNING) silently swallowed every INFO/DEBUG line for the process's entire
    lifetime. Reinstating it does not reopen #3537, which was uvicorn's OWN
    lines being handled twice.
    """
    level = resolve_log_level(dev_mode)
    logging.basicConfig(level=_LOG_LEVELS[level], format=_LOG_FORMAT)

    requested = os.environ.get("AURALIS_LOG_LEVEL", "").strip()
    if requested and requested.lower() not in _LOG_LEVELS:
        logger.warning(
            "Ignoring unrecognized AURALIS_LOG_LEVEL=%r (expected one of %s); using %r",
            requested,
            ", ".join(sorted(_LOG_LEVELS)),
            level,
        )
    return level


def configure_sys_path(backend_dir: Path) -> None:
    """Make the ``auralis`` package importable for the current execution context.

    ``backend_dir`` is the directory main.py lives in (auralis-web/backend).
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller bundle (Electron AppImage)
        # Use working directory to find resources (cwd is set to resources/backend by Electron)
        auralis_parent = Path(os.getcwd()).parent
        logger.info("Running as PyInstaller bundle")
        # Absolute path (embeds OS username + install layout) kept at DEBUG only;
        # INFO stays free of it so it's safe to paste into a public bug report
        # (#4366 / #4778).
        logger.debug(f"Adding to sys.path: {auralis_parent}")
        # Append (not insert) so that _MEIPASS — which PyInstaller puts at the front — takes
        # priority over the external resources/auralis/ copy, preventing a stale copy from
        # shadowing the auralis version that was bundled into this executable.
        sys.path.append(str(auralis_parent))
    elif os.environ.get('ELECTRON_MODE') == '1':
        # Running in Electron but not frozen (shouldn't happen in production)
        auralis_parent = backend_dir.parent
        logger.info("Running in Electron mode (unfrozen)")
        logger.debug(f"Adding to sys.path: {auralis_parent}")
        sys.path.insert(0, str(auralis_parent))
    else:
        # Running in development - auralis package is in ../../..
        auralis_parent = backend_dir.parent.parent
        logger.info("Running in development mode")
        logger.debug(f"Adding to sys.path: {auralis_parent}")
        sys.path.insert(0, str(auralis_parent))


def install_log_sanitizer() -> None:
    """Re-wrap the root handlers' formatters with the sanitizing one (#5393).

    The sanitizing LogRecordFactory (auralis.utils.logging, imported at config
    import time) covers message/args, but traceback text from
    exc_info/logger.exception() is rendered by the handler's Formatter, which
    basicConfig instantiated as a plain Formatter. Attacker-controlled text
    inside an exception message must not be able to forge log lines in the
    persisted electron-log output. Call only after configure_sys_path():
    importing auralis.* earlier breaks the PyInstaller-frozen case.
    """
    from auralis.utils.logging import install_sanitizing_formatter

    install_sanitizing_formatter(fmt=_LOG_FORMAT)
