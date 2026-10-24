"""Regression test for the graceful-shutdown budget constants (#6233).

The lifespan's teardown waits used to be bare inline literals (5 and 10.0,
four sites) with no shared notion of the budget the Electron wrapper's kill
grace must be read against. This locks the constants' existence, defaults
and env-tunability (the AURALIS_* overrides, like the scanner grace).
"""

import sys
from pathlib import Path

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from config import limits  # noqa: E402
from config.limits import (  # noqa: E402
    OBSERVER_JOIN_TIMEOUT_S,
    SHUTDOWN_STEP_TIMEOUT_S,
)


def test_shutdown_budget_constants_exist_with_documented_defaults():
    assert SHUTDOWN_STEP_TIMEOUT_S == 10.0
    assert OBSERVER_JOIN_TIMEOUT_S == 5.0


def test_shutdown_budgets_are_env_tunable(monkeypatch):
    monkeypatch.setenv("AURALIS_SHUTDOWN_STEP_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("AURALIS_OBSERVER_JOIN_TIMEOUT_SECONDS", "2")
    # Re-read the module-level constants the way limits.py computes them.
    from core.env_config import get_int_env

    assert float(get_int_env("AURALIS_SHUTDOWN_STEP_TIMEOUT_SECONDS", 10)) == 3.0
    assert float(get_int_env("AURALIS_OBSERVER_JOIN_TIMEOUT_SECONDS", 5)) == 2.0
    assert limits.SHUTDOWN_STEP_TIMEOUT_S == 10.0  # module constant is import-time


def test_worst_case_teardown_budget_is_the_documented_sum():
    """The CONFIG.md sum: observer join + 3 budgeted steps."""
    assert OBSERVER_JOIN_TIMEOUT_S + 3 * SHUTDOWN_STEP_TIMEOUT_S == 35.0
