"""
Enhancement router dependency plumbing: the per-router RouterDeps binding and the Depends() providers (split from enhancement.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from .dependencies import RouterDeps, provide_connection_manager, require_service, resolve_optional


class _EnhancementDeps:
    def __init__(
        self,
        get_enhancement_settings: Callable[[], dict[str, Any]] | None = None,
        connection_manager: Any = None,
        get_player_state_manager: Callable[[], Any] | None = None,
        get_repository_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.get_enhancement_settings = get_enhancement_settings
        self.connection_manager = connection_manager
        self.get_player_state_manager = get_player_state_manager
        self.get_repository_factory = get_repository_factory


_deps = RouterDeps("enhancement", _EnhancementDeps())


def _get_enhancement_settings() -> dict[str, Any]:
    """The live, shared-by-reference runtime settings dict (#4409).

    Returned as-is, never copied: callers mutate it in place so the change
    propagates to every other holder of the same object.
    """
    return require_service(_deps.current().get_enhancement_settings, "Enhancement settings")()


_get_connection_manager = provide_connection_manager(_deps)


def _get_player_state_manager() -> Any:
    """Optional dependency: None when the factory got no callable for it."""
    return resolve_optional(_deps.current().get_player_state_manager)


def _get_repository_factory() -> Any:
    """Optional dependency: None when the factory got no callable for it."""
    return resolve_optional(_deps.current().get_repository_factory)
