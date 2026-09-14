"""
Caching Module
~~~~~~~~~~~~~~

Intelligent caching system with LRU and TTL support.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .smart_cache import UNCACHEABLE, SmartCache

__all__ = ['SmartCache', 'UNCACHEABLE']
