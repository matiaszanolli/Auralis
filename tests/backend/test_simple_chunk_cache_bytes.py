"""
Regression tests for #3192 — `SimpleChunkCache._current_bytes` accuracy.

Pre-fix bugs:
  * `put()` on an existing key added the new value's bytes to
    `_current_bytes` without subtracting the old value's bytes. After N
    overwrites of the same key, the counter drifted upward by N×size,
    eventually causing premature memory-limit evictions of unrelated
    entries.
  * Sibling: `invalidate_chunk()` removed the entry from the dict but
    never subtracted its bytes — same drift pattern.

Post-fix: both code paths now keep `_current_bytes` exactly in sync with
the actual memory held by `self.cache`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import SimpleChunkCache


def _actual_bytes(cache: SimpleChunkCache) -> int:
    """Sum of nbytes across all entries currently in the cache."""
    return sum(audio.nbytes for audio, _sr in cache.cache.values())


def _audio_of_size(n_samples: int) -> np.ndarray:
    """Stereo float32 array — 8 bytes per sample frame."""
    return np.zeros((n_samples, 2), dtype=np.float32)


# ---------------------------------------------------------------------------
# Overwrite accounting (#3192)
# ---------------------------------------------------------------------------

def test_put_overwrite_does_not_double_count_bytes():
    """Putting the SAME key twice with same-size audio must not double the
    byte counter."""
    cache = SimpleChunkCache(max_chunks=10, max_memory_bytes=10 * 1024 * 1024)

    audio_a = _audio_of_size(1000)
    cache.put(track_id=1, chunk_idx=0, preset='neutral', intensity=0.5,
              audio=audio_a, sample_rate=44100)
    bytes_after_first = cache._current_bytes
    assert bytes_after_first == audio_a.nbytes
    assert _actual_bytes(cache) == bytes_after_first

    # Overwrite the SAME key with same-size audio
    audio_b = _audio_of_size(1000)
    cache.put(track_id=1, chunk_idx=0, preset='neutral', intensity=0.5,
              audio=audio_b, sample_rate=44100)

    # _current_bytes must equal the actual cache memory, NOT 2×audio_b.nbytes
    assert cache._current_bytes == audio_b.nbytes, (
        f"_current_bytes drifted: {cache._current_bytes} vs expected "
        f"{audio_b.nbytes} — #3192 regressed"
    )
    assert _actual_bytes(cache) == cache._current_bytes


def test_put_overwrite_with_different_size_tracks_real_memory():
    """Overwriting with a different-size buffer must shrink/grow the
    counter to match actual memory exactly."""
    cache = SimpleChunkCache(max_chunks=10, max_memory_bytes=10 * 1024 * 1024)

    cache.put(track_id=1, chunk_idx=0, preset='neutral', intensity=0.5,
              audio=_audio_of_size(2000), sample_rate=44100)
    # Overwrite with a SMALLER buffer
    cache.put(track_id=1, chunk_idx=0, preset='neutral', intensity=0.5,
              audio=_audio_of_size(500), sample_rate=44100)

    assert cache._current_bytes == _actual_bytes(cache)
    assert cache._current_bytes == 500 * 8       # 500 samples × 8 bytes/frame

    # And overwriting again with a LARGER buffer
    cache.put(track_id=1, chunk_idx=0, preset='neutral', intensity=0.5,
              audio=_audio_of_size(3000), sample_rate=44100)
    assert cache._current_bytes == _actual_bytes(cache)
    assert cache._current_bytes == 3000 * 8


def test_repeated_overwrites_stay_stable():
    """100 overwrites of the same key with the same-size buffer must keep
    `_current_bytes` constant at 1× the buffer size — pre-fix this would
    be ~100× the buffer size and would trigger premature eviction of
    unrelated entries."""
    cache = SimpleChunkCache(max_chunks=10, max_memory_bytes=10 * 1024 * 1024)

    audio = _audio_of_size(1000)
    expected = audio.nbytes
    for _ in range(100):
        cache.put(track_id=1, chunk_idx=0, preset='neutral', intensity=0.5,
                  audio=_audio_of_size(1000), sample_rate=44100)

    assert cache._current_bytes == expected
    assert _actual_bytes(cache) == expected
    assert len(cache.cache) == 1


def test_overwrite_does_not_evict_unrelated_entries():
    """The pre-fix counter drift could trigger memory-limit evictions of
    SIBLING entries because the limit check thought we were over budget.
    Verify: a key overwrite never evicts a different key."""
    # Memory budget tight enough that the pre-fix drift would push us over.
    audio_size = _audio_of_size(1000).nbytes      # 8000 bytes per entry
    # Budget: just enough for 3 entries
    cache = SimpleChunkCache(max_chunks=50, max_memory_bytes=audio_size * 3 + 100)

    # Insert 3 distinct entries — fill the budget exactly
    for chunk_idx in (0, 1, 2):
        cache.put(track_id=1, chunk_idx=chunk_idx, preset='neutral', intensity=0.5,
                  audio=_audio_of_size(1000), sample_rate=44100)
    assert len(cache.cache) == 3

    # Overwrite chunk 0 many times — pre-fix, the byte drift triggers
    # eviction of chunk 1 and chunk 2.
    for _ in range(20):
        cache.put(track_id=1, chunk_idx=0, preset='neutral', intensity=0.5,
                  audio=_audio_of_size(1000), sample_rate=44100)

    assert len(cache.cache) == 3, (
        f"Expected 3 entries (no spurious eviction), got {len(cache.cache)}"
    )
    assert cache._current_bytes == _actual_bytes(cache)


# ---------------------------------------------------------------------------
# invalidate_chunk sibling fix
# ---------------------------------------------------------------------------

def test_invalidate_chunk_subtracts_bytes():
    """Pre-fix invalidate_chunk popped the entry but didn't subtract its
    bytes — _current_bytes drifted upward across invalidations too."""
    cache = SimpleChunkCache(max_chunks=10, max_memory_bytes=10 * 1024 * 1024)

    cache.put(track_id=1, chunk_idx=0, preset='neutral', intensity=0.5,
              audio=_audio_of_size(1000), sample_rate=44100)
    cache.put(track_id=1, chunk_idx=1, preset='neutral', intensity=0.5,
              audio=_audio_of_size(1500), sample_rate=44100)

    assert cache._current_bytes == _actual_bytes(cache)
    before = cache._current_bytes

    cache.invalidate_chunk(track_id=1, chunk_idx=0, preset='neutral', intensity=0.5)

    assert cache._current_bytes == before - (1000 * 8), (
        f"_current_bytes must decrease by the evicted entry's bytes"
    )
    assert cache._current_bytes == _actual_bytes(cache)


def test_invalidate_chunk_noop_does_not_change_bytes():
    """Invalidating a non-existent key must be a no-op for the counter too."""
    cache = SimpleChunkCache(max_chunks=10, max_memory_bytes=10 * 1024 * 1024)

    cache.put(track_id=1, chunk_idx=0, preset='neutral', intensity=0.5,
              audio=_audio_of_size(1000), sample_rate=44100)
    before = cache._current_bytes

    # Invalidate a key that doesn't exist
    cache.invalidate_chunk(track_id=999, chunk_idx=999, preset='neutral', intensity=0.5)

    assert cache._current_bytes == before
    assert cache._current_bytes == _actual_bytes(cache)


# ---------------------------------------------------------------------------
# Invariant: _current_bytes always matches actual cache memory
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sequence", [
    # Mix of puts, overwrites, and invalidates
    [('put', 1, 0, 100), ('put', 1, 1, 200), ('put', 1, 0, 50),
     ('inv', 1, 0), ('put', 1, 2, 300)],
    # Many overwrites + occasional new keys
    [('put', 1, 0, 100), ('put', 1, 0, 100), ('put', 1, 0, 100),
     ('put', 1, 1, 200), ('put', 1, 0, 50)],
    # Invalidate-only patterns
    [('put', 1, i, 100 * (i + 1)) for i in range(5)] +
    [('inv', 1, i) for i in range(5)],
])
def test_current_bytes_matches_actual_memory_under_arbitrary_sequence(sequence):
    """For any sequence of put/invalidate operations, the counter must
    exactly equal the sum of nbytes across live cache entries."""
    cache = SimpleChunkCache(max_chunks=50, max_memory_bytes=100 * 1024 * 1024)

    for op in sequence:
        if op[0] == 'put':
            _, tid, cidx, n_samples = op
            cache.put(track_id=tid, chunk_idx=cidx, preset='neutral', intensity=0.5,
                      audio=_audio_of_size(n_samples), sample_rate=44100)
        else:  # 'inv'
            _, tid, cidx = op
            cache.invalidate_chunk(track_id=tid, chunk_idx=cidx,
                                   preset='neutral', intensity=0.5)

        assert cache._current_bytes == _actual_bytes(cache), (
            f"Counter drifted after op {op}: "
            f"_current_bytes={cache._current_bytes}, actual={_actual_bytes(cache)}"
        )
