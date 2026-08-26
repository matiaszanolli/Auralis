"""
Regression tests for env-var-overridable HTTP rate limits (#3901)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RateLimitMiddleware._RATE_LIMITS used to hard-code (max_requests,
window_seconds) per path prefix with no override mechanism -- a power user
running a large library import or batch processing session could hit them
legitimately, and the 2/minute scan limit in particular made re-triggering a
scan after an error one click from a 429.

config/limits.py now sources each value from core.env_config.get_int_env, so
an operator can raise them via env var without a code edit + rebuild.
get_int_env's own parsing/fallback behavior is exhaustively covered by
test_env_config.py; these tests only verify the specific env-var-name ->
constant wiring in config/limits.py itself.

Reloading config.limits is safe (unlike config.routes, flagged elsewhere as
an import-cache hazard): it is a pure-constants module with no side effects
beyond recomputing the get_int_env() calls.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config import limits as limits_module  # noqa: E402


@pytest.fixture(autouse=True)
def _reload_limits_after_test():
    """Every test reloads config.limits with an env var set; always reload
    once more afterwards (with the var cleared) so later tests in the same
    session see the real default again."""
    yield
    importlib.reload(limits_module)


@pytest.mark.parametrize(
    "env_var,attr,default",
    [
        ("AURALIS_RATE_LIMIT_UPLOAD_MAX", "RATE_LIMIT_UPLOAD_MAX", 5),
        ("AURALIS_RATE_LIMIT_UPLOAD_WINDOW", "RATE_LIMIT_UPLOAD_WINDOW", 60),
        ("AURALIS_RATE_LIMIT_PROCESSING_MAX", "RATE_LIMIT_PROCESSING_MAX", 10),
        ("AURALIS_RATE_LIMIT_PROCESSING_WINDOW", "RATE_LIMIT_PROCESSING_WINDOW", 60),
        ("AURALIS_RATE_LIMIT_SCAN_MAX", "RATE_LIMIT_SCAN_MAX", 2),
        ("AURALIS_RATE_LIMIT_SCAN_WINDOW", "RATE_LIMIT_SCAN_WINDOW", 60),
        ("AURALIS_RATE_LIMIT_SIMILARITY_MAX", "RATE_LIMIT_SIMILARITY_MAX", 20),
        ("AURALIS_RATE_LIMIT_SIMILARITY_WINDOW", "RATE_LIMIT_SIMILARITY_WINDOW", 60),
    ],
)
class TestEachRateLimitIsEnvOverridable:
    def test_default_matches_the_documented_value(self, monkeypatch, env_var, attr, default):
        monkeypatch.delenv(env_var, raising=False)
        importlib.reload(limits_module)
        assert getattr(limits_module, attr) == default

    def test_env_var_overrides_the_default(self, monkeypatch, env_var, attr, default):
        override = default * 3 + 7  # distinct from the default either way
        monkeypatch.setenv(env_var, str(override))
        importlib.reload(limits_module)
        assert getattr(limits_module, attr) == override


class TestRateLimitMiddlewareSourcesFromLimitsModule:
    """RateLimitMiddleware._RATE_LIMITS must be built from config/limits.py's
    constants, not re-hardcoded.

    Deliberately does NOT read config.limits' current attribute values here:
    `from .limits import X` in config/middleware.py bound `X` once, at
    whatever time config.middleware was first imported (module-level names
    are independent objects, not live references) -- so the class attribute
    below reflects that one-time snapshot regardless of how many times
    config.limits gets reloaded afterwards by the tests above. Comparing
    against the documented defaults directly, rather than against
    config.limits' current (possibly-reloaded-by-a-sibling-test) state,
    avoids exactly the cross-test reload-ordering flakiness that made an
    earlier version of this test order-dependent."""

    def test_rate_limits_dict_matches_the_documented_defaults(self):
        from config import middleware

        assert middleware.RateLimitMiddleware._RATE_LIMITS == {
            "/api/files/upload": (5, 60),
            "/api/processing": (10, 60),
            "/api/library/scan": (2, 60),
            "/api/similarity": (20, 60),
        }
