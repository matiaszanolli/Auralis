"""
Canonical intensity precision for every chunk-cache key and on-disk filename (#5474).

A leaf module on purpose: both ``chunk_cache_manager`` and
``encoding.wav_encoder`` need it, and ``chunk_cache_manager`` imports from the
``encoding`` package, so defining it in ``chunk_cache_manager`` made importing
that module first (``chunk_processor_init`` does) a circular import.

Each tier used to format intensity at its own precision -- .1f in cache/models.py,
the raw float in the on-disk key and WAV filename -- so two requests in the same
0.1 bucket could be served audio rendered for a different off-grid intensity,
and float noise (0.30000000000000004) minted its own unreachable disk entries.
Quantise once here; every consumer imports this function rather than formatting
intensity itself.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

INTENSITY_KEY_DECIMALS = 1


def intensity_cache_key(intensity: float) -> float:
    """Bucket an intensity to the chunk cache's canonical 0.1 granularity."""
    return round(float(intensity), INTENSITY_KEY_DECIMALS)
