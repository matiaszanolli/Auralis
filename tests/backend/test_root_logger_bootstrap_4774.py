# -*- coding: utf-8 -*-
"""
main.py configures the root logger before building the app (#4774)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

(The configuration itself lives in config/bootstrap.py since #5834; main.py
calls it first.)

#3537 removed `logging.basicConfig` from main.py on the theory that
`uvicorn.run()` installs handlers on the root logger, and a second
`basicConfig` call duplicated every line. Checked against uvicorn's actual
`LOGGING_CONFIG`: it only ever configures the "uvicorn"/"uvicorn.access"
loggers (propagate=False) and "uvicorn.error" (stops at "uvicorn"'s
handler) -- never root. Every module logger in this codebase propagates
straight to root, which had no handler at any point in the process's
lifetime, so `logging.lastResort` (level WARNING) silently ate all 20
router-registration confirmations in config/routes.py, plus the sys.path
bootstrap's own INFO/DEBUG lines just below where this now sits.

These are source-level checks (matching this file's sibling
`test_main_py_sys_path_bootstrap_still_logs_path_at_debug` for the same
module), not an in-process import: main.py is already imported by many other
backend test modules in this suite, and `logging.basicConfig()` is a no-op on
a second call in the same process, so a naive "root has a handler after
`import main`" assertion would pass regardless of whether this fix is
present, depending on test order. A fresh `python main.py`/`import main` was
verified manually instead (see the commit): router-registration lines now
appear, and uvicorn's own "Uvicorn running on ..." line still appears exactly
once (no #3537 regression).
"""

import re
from pathlib import Path

_BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
_MAIN_PY = _BACKEND / "main.py"
_BOOTSTRAP_PY = _BACKEND / "config" / "bootstrap.py"


def _source() -> str:
    """The module that owns the logging configuration."""
    return _BOOTSTRAP_PY.read_text()


class TestLoggingConfiguredBeforeAppConstruction:
    def test_basic_config_is_called(self):
        source = _source()
        assert re.search(r'logging\.basicConfig\(', source), (
            "config/bootstrap.py no longer calls logging.basicConfig() -- "
            "router-registration INFO/DEBUG logs will be silently dropped by "
            "logging.lastResort again"
        )

    def test_main_configures_logging_before_the_sys_path_bootstrap(self):
        """The sys.path bootstrap's own logger.info/.debug calls must not fire
        before basicConfig -- they were part of what #4774 found silently
        dropped -- and neither may run after the first config.app import."""
        source = _MAIN_PY.read_text()
        logging_pos = source.index("configure_logging(")
        path_pos = source.index("configure_sys_path(")
        first_app_import = source.index("from config.app import")
        assert logging_pos < path_pos < first_app_import, (
            "main.py must call configure_logging() before configure_sys_path(), "
            "and both before importing config.app"
        )

    def test_level_is_gated_on_dev_mode_not_hardcoded(self):
        """Router-registration confirmations are INFO; DEBUG detail (e.g.
        config/routes.py's 'Health router registered') should additionally
        surface in dev mode, mirroring is_dev_mode()'s own --dev/env-var check."""
        from config.bootstrap import resolve_log_level

        assert 'AURALIS_DEV_MODE' in _source(), (
            "the dev-mode env var is checked nowhere near the logging bootstrap"
        )
        assert resolve_log_level(True, env={}) == "debug"
        assert resolve_log_level(False, env={}) == "info"

    def test_format_includes_logger_name_and_level(self):
        """A bare basicConfig() default format ('%(message)s') would make
        every propagated line indistinguishable from a bare print -- assert
        the format string carries enough to diagnose which module logged
        what at what severity."""
        from config.bootstrap import _LOG_FORMAT

        assert '%(name)s' in _LOG_FORMAT
        assert '%(levelname)s' in _LOG_FORMAT
        assert 'format=_LOG_FORMAT' in _source()

    def test_does_not_reintroduce_the_false_uvicorn_root_logger_claim(self):
        """The #3537 comment this replaced asserted uvicorn.run() configures
        the root logger. It doesn't (checked against uvicorn.config.LOGGING_CONFIG:
        only 'uvicorn'/'uvicorn.access'/'uvicorn.error', never ''/root) -- pin
        that the corrected rationale doesn't quietly regress back to the old
        claim on some future edit."""
        for source in (_source(), _MAIN_PY.read_text()):
            assert 'installs its own logging configuration with handlers on the root logger' not in source
