"""
Regression tests for the byte-bounded audio-file cache (#3830).

`_load_audio_cached` was `@lru_cache(maxsize=8)` — bounded by entry count, so a
handful of large lossless files pinned >1 GB with no eviction, and concurrent
streams of the same fresh file decoded it twice. It's now `_AudioFileCache`: a
thread-safe LRU with a hard byte cap (mirroring SimpleChunkCache) plus a
per-key in-flight lock that collapses concurrent decodes into one.
"""

import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

import routers.wav_streaming as wav_streaming
from routers.wav_streaming import _AudioFileCache


@pytest.fixture
def fake_load_audio(monkeypatch):
    """Patch unified_loader.load_audio with a counting, configurable fake.

    Returns a small helper exposing `.count` and a `.set_array(arr)` so each
    test controls the decoded payload (and its nbytes).
    """
    import auralis.io.unified_loader as ul

    state = {"count": 0, "array": np.zeros((100, 2), dtype=np.float32), "delay": 0.0}

    def _fake(filepath):
        state["count"] += 1
        if state["delay"]:
            time.sleep(state["delay"])
        return state["array"], 44100

    monkeypatch.setattr(ul, "load_audio", _fake)
    return state


def test_cache_hit_decodes_once(fake_load_audio):
    cache = _AudioFileCache(max_bytes=10 * 1024 * 1024)

    a1, sr1 = cache.get_or_load("/x/a.wav", 1.0)
    a2, sr2 = cache.get_or_load("/x/a.wav", 1.0)

    assert fake_load_audio["count"] == 1, "second call must hit cache, not re-decode"
    assert a1 is a2 and sr1 == sr2 == 44100


def test_cached_array_is_read_only(fake_load_audio):
    cache = _AudioFileCache()
    audio, _ = cache.get_or_load("/x/a.wav", 1.0)
    assert not audio.flags.writeable


def test_mtime_change_triggers_reload(fake_load_audio):
    cache = _AudioFileCache()
    cache.get_or_load("/x/a.wav", 1.0)
    cache.get_or_load("/x/a.wav", 2.0)  # re-encoded → different key
    assert fake_load_audio["count"] == 2


def test_byte_bounded_eviction(fake_load_audio):
    """Eviction is by BYTES, not entry count — the regression at the heart of
    #3830 (lru_cache(maxsize=8) bounded only by count)."""
    # Each fake decode is 100*2*4 = 800 bytes. Cap at 1000 → only one fits.
    fake_load_audio["array"] = np.zeros((100, 2), dtype=np.float32)
    cache = _AudioFileCache(max_bytes=1000)

    cache.get_or_load("/x/a.wav", 1.0)
    assert cache._current_bytes == 800
    cache.get_or_load("/x/b.wav", 1.0)  # 800 + 800 > 1000 → evict a

    assert cache._current_bytes <= 1000
    assert len(cache._cache) == 1
    assert ("/x/b.wav", 1.0) in cache._cache
    assert ("/x/a.wav", 1.0) not in cache._cache


def test_lru_order_evicts_oldest(fake_load_audio):
    """A cache HIT refreshes recency so the genuinely-oldest entry is evicted."""
    fake_load_audio["array"] = np.zeros((100, 2), dtype=np.float32)  # 800 B each
    cache = _AudioFileCache(max_bytes=1800)  # fits two

    cache.get_or_load("/x/a.wav", 1.0)
    cache.get_or_load("/x/b.wav", 1.0)
    cache.get_or_load("/x/a.wav", 1.0)   # touch a → b is now oldest
    cache.get_or_load("/x/c.wav", 1.0)   # evict the LRU (b)

    keys = {k for k in cache._cache}
    assert ("/x/a.wav", 1.0) in keys
    assert ("/x/c.wav", 1.0) in keys
    assert ("/x/b.wav", 1.0) not in keys


def test_oversized_file_is_still_cached(fake_load_audio):
    """A single file larger than the cap is kept (we need it to stream), matching
    SimpleChunkCache's keep-the-newcomer behaviour."""
    fake_load_audio["array"] = np.zeros((1000, 2), dtype=np.float32)  # 8000 B
    cache = _AudioFileCache(max_bytes=1000)

    audio, _ = cache.get_or_load("/x/big.wav", 1.0)
    assert ("/x/big.wav", 1.0) in cache._cache
    assert cache._current_bytes == audio.nbytes


def test_clear_empties_cache(fake_load_audio):
    cache = _AudioFileCache()
    cache.get_or_load("/x/a.wav", 1.0)
    cache.clear()
    assert len(cache._cache) == 0
    assert cache._current_bytes == 0


def test_concurrent_same_file_decodes_once(fake_load_audio):
    """N threads requesting the same fresh file must share ONE decode (#3830)."""
    fake_load_audio["delay"] = 0.05  # widen the race window
    cache = _AudioFileCache(max_bytes=10 * 1024 * 1024)

    n = 8
    barrier = threading.Barrier(n)
    results: list[tuple] = []
    results_lock = threading.Lock()

    def worker():
        barrier.wait()  # all start together
        audio, sr = cache.get_or_load("/x/same.wav", 1.0)
        with results_lock:
            results.append((id(audio), sr))

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert fake_load_audio["count"] == 1, (
        f"expected a single shared decode, got {fake_load_audio['count']}"
    )
    # Every caller received the identical cached array object.
    assert len({r[0] for r in results}) == 1
    # The in-flight registry is cleaned up afterwards.
    assert cache._inflight == {}


def test_module_level_cache_is_byte_bounded_instance():
    """The router uses the new cache, not lru_cache."""
    assert isinstance(wav_streaming._audio_file_cache, _AudioFileCache)
    assert not hasattr(wav_streaming, "_load_audio_cached")
