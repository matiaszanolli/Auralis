"""StreamlinedCacheAdapter was dead code carrying an unbounded in-memory
audio cache (#4758).

`cache/adapter.py`'s `_temp_chunk_cache` dict had no size/byte cap or
eviction, unlike its live counterpart `SimpleChunkCache` (capped at 50
chunks / 512 MB) — a dormant memory-leak hazard, reachable only if a future
caller wired the class in via its `cache/__init__.py` re-export. The class
had zero production callers (grep across auralis-web/ and tests/ found only
the definition and the __init__.py export), so it was removed outright per
the project's No-variants principle rather than given a bounded cache to
maintain in parallel with SimpleChunkCache.
"""

import sys
from pathlib import Path

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


class TestStreamlinedCacheAdapterRemoved:
    def test_adapter_module_no_longer_exists(self):
        import importlib

        try:
            importlib.import_module("cache.adapter")
        except ModuleNotFoundError:
            pass
        else:
            raise AssertionError("cache/adapter.py should have been deleted (#4758)")

    def test_cache_package_no_longer_exports_the_adapter(self):
        import cache

        assert not hasattr(cache, "StreamlinedCacheAdapter")
        assert "StreamlinedCacheAdapter" not in cache.__all__

    def test_streamlined_cache_manager_is_unaffected(self):
        """The live, bounded cache the adapter used to wrap must still work
        normally after the dead adapter's removal."""
        import cache

        assert cache.StreamlinedCacheManager is not None
        assert cache.streamlined_cache_manager is not None
