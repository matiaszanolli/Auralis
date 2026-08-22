#!/usr/bin/env python3

"""
Last-Content-Profile Registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tiny process-wide cache of each preset's most recent HybridProcessor content
profile, used by the ``/api/processing/parameters`` visualizer endpoint.
Extracted from ``chunked_processor.py`` (#4245) — bookkeeping unrelated to the
chunk-streaming pipeline itself.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import threading
from typing import Any

# Global cache for last content profiles (used by visualizer API)
# Maps preset name -> last_content_profile dict
_last_content_profiles: dict[str, Any] = {}
# Guards _last_content_profiles: store_content_profile() writes it from
# concurrent asyncio.to_thread workers across streams, while
# get_last_content_profile() reads it from the event-loop thread for
# /api/processing/parameters (#4341).
_last_content_profiles_lock = threading.Lock()


def store_content_profile(preset: str, profile: dict[str, Any]) -> None:
    """Record ``profile`` as the latest content profile for ``preset``.

    Known limitation (#4601): keyed by preset name ONLY — no ws_id or track
    dimension — so two concurrent streams on the same preset overwrite each
    other's profile. See ``get_last_content_profile()`` for the read side.
    """
    with _last_content_profiles_lock:
        _last_content_profiles[preset.lower()] = profile


def get_last_content_profile(preset: str) -> dict[str, Any] | None:
    """
    Get the last content profile for a given preset.
    Used by /api/processing/parameters endpoint to show real processing data.

    Args:
        preset: Preset name (e.g., "adaptive", "gentle", "warm", etc.)

    Returns:
        Last content profile dict or None if not available

    Known limitation (#4601): the map is keyed by preset name ONLY — no ws_id or
    track dimension — so two concurrent streams on the same preset overwrite each
    other's profile. Harmless for the desktop single-client app this ships as,
    but it is why the caller must pass the preset the STREAM is running, not a
    stale global; `handle_play_enhanced` now writes the accepted preset back into
    `enhancement_settings` so the two cannot diverge.
    """
    with _last_content_profiles_lock:
        value = _last_content_profiles.get(preset.lower())
    if isinstance(value, dict):
        return value
    return None
