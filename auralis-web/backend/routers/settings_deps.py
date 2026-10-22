"""
Settings router dependency plumbing (split from settings.py, #5832).

The handlers are module-level functions, so they reach the getters one
``create_settings_router()`` call received through ``RouterDeps`` instead of
closure capture (the #4670 / #5166 pattern).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from fastapi import Depends

from .dependencies import RouterDeps, require_service


class _SettingsDeps:
    def __init__(
        self,
        get_settings_repo: Callable[[], Any] = lambda: None,
        get_auto_scanner: Callable[[], Any] | None = None,
        get_enhancement_settings: Callable[[], dict[str, Any]] | None = None,
        connection_manager: Any = None,
        get_library_database: Callable[[], Any] | None = None,
    ) -> None:
        self.get_settings_repo = get_settings_repo
        self.get_auto_scanner = get_auto_scanner
        self.get_enhancement_settings = get_enhancement_settings
        self.connection_manager = connection_manager
        self.get_library_database = get_library_database


_deps = RouterDeps("settings", _SettingsDeps())


def _get_deps() -> _SettingsDeps:
    return _deps.current()


def _get_repo(deps: _SettingsDeps = Depends(_get_deps)) -> Any:
    """Resolve the SettingsRepository per request (503 if unavailable)."""
    return require_service(deps.get_settings_repo(), "Settings")
