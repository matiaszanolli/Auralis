"""Regression tests for the resolved process log level (#5065).

`uvicorn.run()` was called with a hardcoded `log_level="info"` and there was no
way to ask for DEBUG at all. The level now comes from one place --
`main.resolve_log_level()` -- which feeds BOTH `logging.basicConfig()` (the
level that actually gates every `logger.debug` in the backend, since uvicorn
never touches the root logger) and `uvicorn.run(log_level=...)`.

The non-dev default must stay "info": #4366/#4778 demoted absolute paths, which
embed the OS username and install layout, to DEBUG specifically so INFO-level
output stays safe to paste into a public bug report.
"""

import inspect
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import main


# ---------------------------------------------------------------------------
# Default level per mode
# ---------------------------------------------------------------------------

def test_dev_mode_defaults_to_debug():
    assert main.resolve_log_level(True, env={}) == "debug"


def test_production_defaults_to_info():
    """The #4366/#4778 public-bug-report safety property: no DEBUG by default."""
    assert main.resolve_log_level(False, env={}) == "info"


def test_unrelated_env_does_not_change_the_default():
    env = {"AURALIS_DEV_MODE": "1", "PATH": "/usr/bin"}
    assert main.resolve_log_level(False, env=env) == "info"
    assert main.resolve_log_level(True, env=env) == "debug"


# ---------------------------------------------------------------------------
# AURALIS_LOG_LEVEL override
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["debug", "DEBUG", " Debug ", "trace"])
def test_env_var_can_raise_the_level_on_a_packaged_build(value):
    """Support sessions can opt into DEBUG without enabling dev mode."""
    assert main.resolve_log_level(False, env={"AURALIS_LOG_LEVEL": value}) == value.strip().lower()


def test_env_var_can_lower_the_level_in_dev_mode():
    assert main.resolve_log_level(True, env={"AURALIS_LOG_LEVEL": "warning"}) == "warning"


@pytest.mark.parametrize("value", ["", "   ", "verbose", "DEBUGG", "10"])
def test_unrecognized_value_falls_back_to_the_mode_default(value):
    """A typo must not crash startup, and must not silently widen disclosure."""
    assert main.resolve_log_level(False, env={"AURALIS_LOG_LEVEL": value}) == "info"
    assert main.resolve_log_level(True, env={"AURALIS_LOG_LEVEL": value}) == "debug"


def test_os_environ_is_the_default_source(monkeypatch):
    monkeypatch.setenv("AURALIS_LOG_LEVEL", "error")
    assert main.resolve_log_level(True) == "error"
    monkeypatch.delenv("AURALIS_LOG_LEVEL")
    assert main.resolve_log_level(True) == "debug"
    assert main.resolve_log_level(False) == "info"


# ---------------------------------------------------------------------------
# The resolved name must be usable by both consumers
# ---------------------------------------------------------------------------

def test_every_level_name_maps_to_a_numeric_level_for_basicconfig():
    """basicConfig() needs a number; uvicorn needs the name. One table serves both."""
    assert main._LOG_LEVELS["debug"] == logging.DEBUG
    assert main._LOG_LEVELS["info"] == logging.INFO
    assert main._LOG_LEVELS["trace"] < logging.DEBUG
    for name in main._LOG_LEVELS:
        assert isinstance(main._LOG_LEVELS[name], int)


def test_every_level_name_is_accepted_by_uvicorn():
    from uvicorn.config import LOG_LEVELS

    assert set(main._LOG_LEVELS) <= set(LOG_LEVELS)


def test_uvicorn_run_is_passed_the_resolved_level_not_a_literal():
    """The call site must not re-hardcode a level (the #5065 bug itself)."""
    source = inspect.getsource(main)
    # rindex: the word "uvicorn.run()" also appears in the module's header
    # comments; the real call site is the last occurrence.
    run_call = source[source.rindex("uvicorn.run("):]
    run_call = run_call[: run_call.index(")\n")]
    assert "log_level=_log_level" in run_call
    assert 'log_level="info"' not in run_call


def test_module_level_resolution_matches_the_configured_root_level():
    """main._log_level is what basicConfig() was given, not an unused value."""
    assert main._log_level in main._LOG_LEVELS
    assert main._log_level == main.resolve_log_level(main._dev_mode)
