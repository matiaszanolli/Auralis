#!/usr/bin/env python3

"""
Mastering-Targets Content Hash
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Single source of truth for turning a ``mastering_targets`` dict into a short,
stable cache-key component.

#3720 established that mastering targets belong in a cache key: they change
the DSP branch ``AudioProcessingPipeline.apply_enhancement`` takes (fixed
targets applied, per-chunk fingerprint analysis disabled), so two callers
requesting the same (track, preset, intensity) with DIFFERENT targets must not
share a cached artifact. That reasoning was applied only to
``ProcessorFactory``'s processor cache; #4666 extends it to the chunk caches
(``ChunkCacheManager`` in-memory keys, the ``WAVEncoder`` on-disk filename, and
``SimpleChunkCache``).

Every one of those tiers must derive the hash IDENTICALLY — two different
hashes of the same targets would defeat the point — so the implementation lives
here rather than being copied per tier.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: Sentinel used when no mastering targets are present. Callers that never
#: supply targets keep sharing one cache entry per (track, preset, ...),
#: preserving the pre-#4666 cache-hit behaviour for the common case.
NO_TARGETS = "none"


def get_targets_hash(mastering_targets: dict[str, Any] | None) -> str:
    """Content hash of ``mastering_targets`` for use in a cache key.

    Returns :data:`NO_TARGETS` when targets are absent.

    ``sort_keys=True`` is load-bearing: two dicts with equal content but
    different key insertion order MUST hash identically, or the chunk cache
    would miss on every request and the on-disk tier would fill with
    duplicate-content WAVs.
    """
    if mastering_targets is None:
        return NO_TARGETS
    try:
        payload = json.dumps(mastering_targets, sort_keys=True, default=str)
    except (TypeError, ValueError):
        # Fall back to a stable repr if the dict contains non-JSON values.
        payload = repr(sorted(mastering_targets.items()))
    return hashlib.md5(payload.encode()).hexdigest()
