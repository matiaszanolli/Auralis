"""
Hybrid Processor Convenience API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Process-wide cached ``process_adaptive`` / ``process_reference`` /
``process_hybrid`` free functions, re-exported from the ``auralis`` package.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

These wrap :class:`~auralis.core.hybrid_processor.HybridProcessor` behind a
bounded LRU cache of already-initialised processors, so a caller that just
wants "master this array" does not pay the ~500ms construction cost per call.
They live here rather than in ``hybrid_processor.py`` (#4266) so that the class
file holds only the class: the free-function API and the class API are two
surfaces that have to stay in sync, and keeping them in one module made that
easy to miss.
"""

import threading
from collections import OrderedDict
from copy import deepcopy

import numpy as np

from ..utils.logging import debug
from .config import UnifiedConfig
from .hybrid_processor import HybridProcessor


# Module-level processor cache for convenience functions
# Caches HybridProcessor instances to avoid expensive re-initialization
# LRU-eviction cap: prevents unbounded memory growth in long-running servers (#2161)
_PROCESSOR_CACHE_MAX_SIZE: int = 10
_processor_cache: OrderedDict[str, HybridProcessor] = OrderedDict()
# Lock protecting _processor_cache against concurrent check-and-insert races (#2314)
_processor_cache_lock: threading.Lock = threading.Lock()


def _get_or_create_processor(config: UnifiedConfig | None, mode: str) -> HybridProcessor:
    """
    Get or create a cached HybridProcessor instance

    Args:
        config: Optional custom config, or None to use default
        mode: Processing mode ("adaptive", "reference", or "hybrid")

    Returns:
        Cached or newly created HybridProcessor instance
    """
    # Preserve identity-based cache compatibility while giving each cached
    # processor its own config snapshot below (#4827).
    cache_key = f"{id(config)}_{mode}" if config is not None else f"default_{mode}"

    with _processor_cache_lock:
        cached = _processor_cache.get(cache_key)
        if cached is not None:
            _processor_cache.move_to_end(cache_key)
            debug(f"Using cached HybridProcessor for mode={mode}")
            return cached

    # HybridProcessor initialization is expensive and does not touch cache
    # state. Construct outside the global lock so a cold key cannot serialize
    # unrelated callers (#4689). Never mutate a caller-owned config: the same
    # object may back processors for several modes (#4827).
    owned_config = deepcopy(config) if config is not None else UnifiedConfig()
    owned_config.set_processing_mode(mode)  # type: ignore[arg-type]
    processor = HybridProcessor(owned_config)

    evicted: list[tuple[str, HybridProcessor]] = []
    with _processor_cache_lock:
        # A same-key caller may have won the construction race. Keep its
        # established instance and close this redundant processor below.
        cached = _processor_cache.get(cache_key)
        if cached is not None:
            _processor_cache.move_to_end(cache_key)
        else:
            _processor_cache[cache_key] = processor

        # Evict oldest entry when the cache exceeds its maximum size (#2161)
        while len(_processor_cache) > _PROCESSOR_CACHE_MAX_SIZE:
            evicted_key, evicted_processor = _processor_cache.popitem(last=False)
            evicted.append((evicted_key, evicted_processor))

        cache_size = len(_processor_cache)

    if cached is not None:
        processor.close()
        debug(f"Closed redundant HybridProcessor build for mode={mode}")
        return cached

    for evicted_key, evicted_processor in evicted:
        # Dispose outside the cache lock — the ordering #3746 established.
        # close() releases nothing today; see its docstring (#4744).
        evicted_processor.close()
        debug(f"Evicted cached HybridProcessor (cache full): key={evicted_key}")

    debug(f"Created cached HybridProcessor for mode={mode} (cache size: {cache_size})")
    return processor


def process_adaptive(target: np.ndarray,
                    config: UnifiedConfig | None = None) -> np.ndarray:
    """
    Quick adaptive processing function (cached)

    Reuses HybridProcessor instances to avoid expensive re-initialization.
    First call initializes components (~500ms), subsequent calls are instant.
    """
    processor = _get_or_create_processor(config, "adaptive")
    result = processor.process(target)
    assert result is not None
    return result


def process_reference(target: np.ndarray,
                     reference: np.ndarray,
                     config: UnifiedConfig | None = None) -> np.ndarray:
    """
    Quick reference-based processing function (cached)

    Reuses HybridProcessor instances to avoid expensive re-initialization.
    First call initializes components (~500ms), subsequent calls are instant.
    """
    processor = _get_or_create_processor(config, "reference")
    result = processor.process(target, reference)
    assert result is not None
    return result


def process_hybrid(target: np.ndarray,
                  reference: np.ndarray | None = None,
                  config: UnifiedConfig | None = None) -> np.ndarray:
    """
    Quick hybrid processing function (cached)

    Reuses HybridProcessor instances to avoid expensive re-initialization.
    First call initializes components (~500ms), subsequent calls are instant.
    """
    processor = _get_or_create_processor(config, "hybrid")
    result = processor.process(target, reference)
    assert result is not None
    return result
