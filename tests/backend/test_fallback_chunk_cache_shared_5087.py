"""
Regression tests for the shared degraded-mode chunk cache (#5087)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`routers/system.py` builds a fresh `AudioStreamController` per stream request,
passing `get_cache_manager() if get_cache_manager else None`. That returns
None for *every* request once the `streamlined_cache` global fails to
initialise at startup, or after its worker dies and #4318's failure path nulls
both it and `streamlined_worker`.

`AudioStreamController.__init__` used to fall back to `SimpleChunkCache()` —
a fresh instance per controller, i.e. per request. That silently reintroduced
exactly what #3855 eliminated: chunks were never reused across requests (every
scrub/replay a miss), and the memory ceiling multiplied by concurrent streams
(~50 chunks x ~5.3MB x up to MAX_CONCURRENT_STREAMS ~= 2.6GB), with nothing
logged to indicate degraded mode was active.

The fallback is now a process-wide singleton, mirroring
`_global_stream_semaphore`'s #2469 treatment, and logs a WARNING on first use.
"""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import audio_stream_controller as asc
from core.audio_stream_controller import AudioStreamController
from core.chunk_cache import SimpleChunkCache


@pytest.fixture(autouse=True)
def _reset_fallback():
    """The fallback is process-wide by design, so each test must start from a
    clean slate to observe the first-use WARNING and fresh identities."""
    asc._fallback_chunk_cache = None
    yield
    asc._fallback_chunk_cache = None


@pytest.mark.regression
class TestFallbackCacheIsShared:

    def test_two_controllers_share_one_fallback_cache(self):
        """#5087's core acceptance criterion: identity, not just equality."""
        a = AudioStreamController(cache_manager=None)
        b = AudioStreamController(cache_manager=None)

        assert a.cache_manager is b.cache_manager, (
            "each controller got its own SimpleChunkCache — this is the "
            "pre-#3855 per-request cache behaviour reintroduced"
        )
        assert isinstance(a.cache_manager, SimpleChunkCache)

    def test_a_chunk_cached_by_one_stream_is_visible_to_the_next(self):
        """The user-visible consequence: with per-instance caches, a scrub or
        replay served by a second request could never hit."""
        first = AudioStreamController(cache_manager=None)
        second = AudioStreamController(cache_manager=None)

        audio = np.zeros((1024, 2), dtype=np.float32)
        first.cache_manager.put(
            track_id=1, chunk_idx=0, preset="adaptive", intensity=1.0,
            audio=audio, sample_rate=44100,
        )

        hit = second.cache_manager.get(
            track_id=1, chunk_idx=0, preset="adaptive", intensity=1.0,
        )
        assert hit is not None, "second stream missed a chunk the first had cached"

    def test_explicit_cache_manager_is_never_replaced_by_the_fallback(self):
        """The healthy path must be untouched — a real StreamlinedCacheManager
        (or any injected cache) still wins, and using it must not even
        instantiate the fallback."""
        injected = MagicMock()
        controller = AudioStreamController(cache_manager=injected)

        assert controller.cache_manager is injected
        assert asc._fallback_chunk_cache is None, (
            "the fallback was created even though a cache manager was supplied"
        )

    def test_fallback_is_created_only_once(self):
        """Repeated degraded-mode requests must not churn new caches."""
        AudioStreamController(cache_manager=None)
        created = asc._fallback_chunk_cache
        for _ in range(5):
            AudioStreamController(cache_manager=None)

        assert asc._fallback_chunk_cache is created


@pytest.mark.regression
class TestDegradedModeIsObservable:

    def test_first_fallback_use_logs_a_warning(self, caplog):
        """Silent degradation was half the finding: nothing indicated the
        streamlined cache was gone."""
        with caplog.at_level(logging.WARNING, logger=asc.__name__):
            AudioStreamController(cache_manager=None)

        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warnings, "degraded mode was entered with no WARNING logged"
        assert any("SimpleChunkCache" in r.getMessage() for r in warnings), (
            f"WARNING did not identify the fallback: {[r.getMessage() for r in warnings]}"
        )

    def test_warning_is_not_repeated_for_every_stream(self, caplog):
        """One WARNING per process, not one per stream request — the degraded
        path is hit on every request and would otherwise flood the log."""
        with caplog.at_level(logging.WARNING, logger=asc.__name__):
            for _ in range(4):
                AudioStreamController(cache_manager=None)

        fallback_warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING and "SimpleChunkCache" in r.getMessage()
        ]
        assert len(fallback_warnings) == 1, (
            f"expected exactly one fallback WARNING, got {len(fallback_warnings)}"
        )
