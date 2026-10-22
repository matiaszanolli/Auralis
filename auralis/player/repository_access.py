"""
Repository access for the player layer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The one place that turns a ``get_repository_factory`` callable into a
repository factory, or fails loudly (#5783). ``IntegrationManager`` and
``QueueController`` each carried a byte-identical copy of this lookup.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from ..utils.logging import error


def resolve_repository_factory(get_repository_factory: Callable[[], Any]) -> Any:
    """Return the repository factory behind ``get_repository_factory``.

    Raises:
        RuntimeError: the getter is mis-wired (raises ``TypeError`` /
            ``AttributeError``) or returns nothing.
    """
    try:
        factory = get_repository_factory()
        if factory:
            return factory
    except (TypeError, AttributeError) as e:
        error(f"Failed to get repository factory: {e}")

    raise RuntimeError(
        "Repository factory not available. "
        "Ensure get_repository_factory is properly configured during startup."
    )
