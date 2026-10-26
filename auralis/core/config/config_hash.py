"""
Content identity of a configuration (#6087).

One definition of "the same config" for every cache keyed on it: the backend's
``ProcessorFactory`` / ``ProcessorPool`` (via ``processor_cache_key``) and the
``process_adaptive`` / ``process_reference`` processor cache. Keying on
``id(config)`` instead hands a new config the processor built from a freed one
whenever CPython reuses the address.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import hashlib
import json
from typing import Any


def hash_config(config: Any | None) -> str:
    """
    Get hash of config object for cache key.

    Args:
        config: UnifiedConfig instance or None

    Returns:
        Config hash string
    """
    if config is None:
        return "default"

    # Content-based hash so equivalent configs share cache entries
    config_str = json.dumps(config.to_dict(), sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()
