"""
System router dependency plumbing (split from system.py, #5832).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from .dependencies import RouterDeps


class _SystemDeps:
    def __init__(
        self,
        manager: Any = None,
        get_processing_engine: Callable[..., Any] = lambda: None,
        get_repository_factory: Callable[..., Any] | None = None,
        get_state_manager: Callable[..., Any] | None = None,
        get_enhancement_settings: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.manager = manager
        self.get_processing_engine = get_processing_engine
        self.get_repository_factory = get_repository_factory
        self.get_state_manager = get_state_manager
        self.get_enhancement_settings = get_enhancement_settings


_deps = RouterDeps("system", _SystemDeps())


def _get_deps() -> _SystemDeps:
    return _deps.current()
