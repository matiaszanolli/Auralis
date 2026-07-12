"""
Environment-Variable Config Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shared helper for reading integer tuning constants from environment
variables at import time, so per-deployment tuning doesn't require a code
edit + rebuild (#3917).

Deliberately dependency-free (stdlib only) so it can be imported from any
module-level constant assignment without import-order/circularity risk.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import os

logger = logging.getLogger(__name__)


def get_int_env(name: str, default: int, *, min_value: int = 1) -> int:
    """Read an integer config value from an environment variable.

    Falls back to `default` (with a warning) if the variable is unset,
    unparseable, or below `min_value` — a malformed override must never
    crash startup, since these are evaluated at module import time.

    Args:
        name: Environment variable name (e.g. "AURALIS_MAX_CONCURRENT_STREAMS").
        default: Value to use if unset or invalid.
        min_value: Minimum acceptable value; anything lower falls back to default.

    Returns:
        The parsed override, or `default`.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default

    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"{name}={raw!r} is not a valid integer; using default {default}")
        return default

    if value < min_value:
        logger.warning(f"{name}={value} is below minimum {min_value}; using default {default}")
        return default

    return value
