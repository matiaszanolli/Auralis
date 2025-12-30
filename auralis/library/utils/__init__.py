"""
Library utility modules.

Provides shared utilities for library management operations.
"""

from .artist_normalizer import (
    parse_featured_artists,
    normalize_artist_name,
    FEATURING_PATTERNS,
)

__all__ = [
    'parse_featured_artists',
    'normalize_artist_name',
    'FEATURING_PATTERNS',
]
