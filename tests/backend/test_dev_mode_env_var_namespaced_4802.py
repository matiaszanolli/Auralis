"""
Regression: DEV_MODE is namespaced to AURALIS_DEV_MODE (#4802)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

is_dev_mode() used to key off the bare, unnamespaced DEV_MODE environment
variable. Electron launches the backend as a child process inheriting the
user's full environment, so any developer or power user with DEV_MODE=1
exported for an unrelated project would silently run the shipped Auralis
backend in dev mode — re-enabling Swagger/ReDoc/OpenAPI and widening the
CORS/WebSocket origin allowlists, with no log signal that it happened.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.app import is_dev_mode  # noqa: E402


class TestUnnamespacedDevModeNoLongerActivates:
    """The core collision this issue is about: an unrelated, ambient
    DEV_MODE=1 in the inherited environment must not activate dev mode."""

    def test_bare_dev_mode_env_var_is_ignored(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py"])
        monkeypatch.delenv("AURALIS_DEV_MODE", raising=False)
        # Simulates a stray DEV_MODE=1 left exported by an unrelated project.
        monkeypatch.setenv("DEV_MODE", "1")

        assert is_dev_mode() is False

    def test_bare_dev_mode_true_variants_all_ignored(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py"])
        monkeypatch.delenv("AURALIS_DEV_MODE", raising=False)
        for value in ("1", "true", "True", "yes", "YES"):
            monkeypatch.setenv("DEV_MODE", value)
            assert is_dev_mode() is False, f"DEV_MODE={value!r} must not activate dev mode"


class TestNamespacedDevModeActivatesCorrectly:
    def test_auralis_dev_mode_env_var_activates(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py"])
        monkeypatch.setenv("AURALIS_DEV_MODE", "1")

        assert is_dev_mode() is True

    def test_dev_flag_still_activates_without_env_var(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--dev"])
        monkeypatch.delenv("AURALIS_DEV_MODE", raising=False)

        assert is_dev_mode() is True

    def test_neither_flag_nor_env_var_is_production(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py"])
        monkeypatch.delenv("AURALIS_DEV_MODE", raising=False)
        monkeypatch.delenv("DEV_MODE", raising=False)

        assert is_dev_mode() is False


class TestWarningLoggedOnEnvVarActivation:
    def test_env_var_activation_logs_a_warning(self, monkeypatch, caplog):
        monkeypatch.setattr(sys, "argv", ["main.py"])
        monkeypatch.setenv("AURALIS_DEV_MODE", "1")

        with caplog.at_level(logging.WARNING, logger="config.app"):
            assert is_dev_mode() is True

        assert any("AURALIS_DEV_MODE" in record.message for record in caplog.records), (
            "dev mode activated via the env var must log a WARNING so it is "
            "visible in the persisted Electron log sink, not silent"
        )

    def test_dev_flag_activation_does_not_spuriously_warn_about_the_env_var(self, monkeypatch, caplog):
        """--dev is already visible on the launching command line; only the
        env-var path is the silent case this issue is about."""
        monkeypatch.setattr(sys, "argv", ["main.py", "--dev"])
        monkeypatch.delenv("AURALIS_DEV_MODE", raising=False)

        with caplog.at_level(logging.WARNING, logger="config.app"):
            assert is_dev_mode() is True

        assert not any("AURALIS_DEV_MODE" in record.message for record in caplog.records)
