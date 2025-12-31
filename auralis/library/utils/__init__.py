"""
Library utility modules.

Provides shared utilities for library management operations.
"""

from .artist_normalizer import (
    FEATURING_PATTERNS,
    normalize_artist_name,
    parse_featured_artists,
)

__all__ = [
    'parse_featured_artists',
    'normalize_artist_name',
    'FEATURING_PATTERNS',
]
