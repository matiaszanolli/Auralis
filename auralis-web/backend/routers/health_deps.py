"""
Health router dependency plumbing (split from health.py to hold its LOC ceiling).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from .dependencies import RouterDeps


class _HealthDeps:
    def __init__(
        self,
        has_auralis: bool = False,
        get_library_database: Callable[[], Any] | None = None,
        get_player_state_manager: Callable[[], Any] | None = None,
    ) -> None:
        self.has_auralis = has_auralis
        self.get_library_database = get_library_database
        self.get_player_state_manager = get_player_state_manager

    def library_available(self) -> bool:
        return self.has_auralis and (
            self.get_library_database is not None and self.get_library_database() is not None
        )


_deps = RouterDeps("health", _HealthDeps())


def _get_deps() -> _HealthDeps:
    return _deps.current()
