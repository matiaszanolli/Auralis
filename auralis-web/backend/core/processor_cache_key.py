"""
Processor cache identity (split from processor_factory.py, #5833).

The structured key ``ProcessorFactory._processor_cache`` is indexed by, and the
two functions that derive its parts. Kept free of any ProcessorFactory import so
both the factory and its maintenance mixin can depend on it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import NamedTuple

from auralis.core.config.config_hash import hash_config as hash_config


class ProcessorCacheKey(NamedTuple):
    """#3733: structured cache key for `ProcessorFactory._processor_cache`.

    Documenting the key shape as a NamedTuple lets introspection use
    named-attribute access (`key.track_id`, `key.preset`) instead of
    positional indexing (`key[0]`). Adding a new field in the future
    (sample_rate, etc.) stays backward-compatible for callers that
    already use the named fields; positional access would silently shift.

    #4707: `intensity` is deliberately NOT a field. It was keyed on without
    ever reaching the constructed processor — `get_or_create` applies only the
    preset (`config.mastering_profile`) and optional mastering targets, and
    intensity is realised downstream as a dry/wet blend on the processor's
    OUTPUT (`core/audio_processing_pipeline.py`). Two calls differing only in
    intensity therefore built two byte-identical processors and consumed two of
    the 32 LRU slots, so an intensity slider sweep evicted genuinely distinct
    (track, preset) processors and forced redundant 200-500 ms constructions,
    each paying the full 200-500 ms HybridProcessor.__init__ (#3746 — which
    also cited a 5-thread fingerprint executor per build; that executor is
    gone, see #4744, but the construction cost is not).

    Every field here is one the processor actually consumes, matching
    `ProcessorPool.cache_key`. Contrast `targets_hash`, which #3720 added
    precisely because targets DO change the constructed processor.
    """
    track_id: int
    preset: str
    config_hash: str
    targets_hash: str


def build_cache_key(
    track_id: int,
    preset: str,
    config_hash: str,
    targets_hash: str = "none",
) -> ProcessorCacheKey:
    """
    Generate cache key for processor.

    Args:
        track_id: Track ID (use 0 for config-based caching)
        preset: Processing preset
        config_hash: Hash of config object (use "default" for default config)
        targets_hash: Hash of mastering_targets dict (use "none" if absent).
            #3720: included in the key so two callers requesting the same
            (track_id, preset) with DIFFERENT targets get different cached
            processors — eliminates the need to re-apply targets on cache
            hit (which raced with in-flight processing).

    Note:
        `intensity` is intentionally absent (#4707) — see ProcessorCacheKey.

    Returns:
        Cache key tuple
    """
    return ProcessorCacheKey(
        track_id=track_id,
        preset=preset.lower(),
        config_hash=config_hash,
        targets_hash=targets_hash,
    )


# #4666: the targets hasher lives in core/targets_hash.get_targets_hash. The
# chunk caches (ChunkCacheManager keys, the WAVEncoder on-disk filename) key on
# targets too, and every tier must derive the hash IDENTICALLY — so the one
# implementation is shared rather than copied per tier. hash_config itself lives
# in auralis.core.config.config_hash so the library API keys on it too (#6087).
