"""
MemoryPool keys its buffer pool by (shape, dtype) (#4992)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`available_buffers` used to be keyed by `shape` alone, so `get_buffer(shape,
dtype)` popped any buffer of that shape and papered over a dtype mismatch
with `np.asarray(buffer, dtype=dtype)` — a *cast copy*. The caller then held
a different object than the `id()` the pool had recorded in
`allocated_buffers`, so:

  * that entry could never be returned (permanent accounting growth), and
  * once the orphaned original was garbage collected, CPython could reuse its
    `id()` for an unrelated object, which `return_buffer` — keying solely on
    `id()` — would then accept into a possibly-mismatched bucket.

NOTE ON REACHABILITY: this whole cluster is dead. `MemoryPool` is only
constructed by `PerformanceOptimizer.__init__`, and
`PerformanceOptimizer.get_audio_buffer`/`return_audio_buffer` have no callers
in `auralis/` or `auralis-web/`. `PerformanceOptimizer` itself *is*
constructed at import time by `hybrid_processor.py`, but only to wrap
`AdaptiveMode.process` with a profiler (#4524) — the pool is allocated and
never exercised. The wire-up-or-delete decision for this area is tracked by
#4873; #4992 fixed the latent defect without pre-empting it, and these tests
pin the corrected behaviour for whichever way that decision goes.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.optimization.memory.memory_pool import MemoryPool


@pytest.fixture
def pool() -> MemoryPool:
    return MemoryPool(pool_size_mb=1)


def test_same_shape_different_dtype_does_not_reuse(pool):
    """The core defect: a float32 buffer must not satisfy a float64 request."""
    shape = (256,)

    f32 = pool.get_buffer(shape, dtype=np.float32)
    assert f32.dtype == np.float32
    pool.return_buffer(f32)

    f64 = pool.get_buffer(shape, dtype=np.float64)
    assert f64.dtype == np.float64, "pool handed back a stale-dtype buffer"
    # Pre-fix this was a cast *copy* of the pooled float32 buffer.
    assert f64 is not f32


def test_returned_object_is_the_tracked_object(pool):
    """get_buffer must return the very object whose id() it recorded (#4992).

    If it returns a cast copy instead, return_buffer — which keys on id() —
    can never match, and the entry orphans in allocated_buffers forever.
    """
    shape = (128,)
    pool.return_buffer(pool.get_buffer(shape, dtype=np.float32))

    # A pool *hit* is the path that used to cast.
    buffer = pool.get_buffer(shape, dtype=np.float32)
    assert id(buffer) in pool.allocated_buffers

    pool.return_buffer(buffer)
    assert id(buffer) not in pool.allocated_buffers


def test_no_accounting_growth_across_mixed_dtype_cycles(pool):
    """allocated_buffers must return to empty however dtypes interleave."""
    shape = (64,)
    for _ in range(20):
        for dtype in (np.float32, np.float64, np.int16):
            pool.return_buffer(pool.get_buffer(shape, dtype=dtype))

    assert pool.allocated_buffers == set(), (
        f"{len(pool.allocated_buffers)} orphaned entries — get_buffer handed "
        f"back an object other than the one it tracked"
    )


def test_pool_hit_reuses_the_same_object(pool):
    """The pool must still actually pool — the fix must not disable reuse."""
    shape = (32,)
    first = pool.get_buffer(shape, dtype=np.float32)
    pool.return_buffer(first)
    second = pool.get_buffer(shape, dtype=np.float32)

    assert second is first, "matching shape+dtype request should reuse the buffer"


def test_returned_buffer_is_zeroed(pool):
    """Existing contract: return_buffer clears before pooling."""
    shape = (16,)
    buffer = pool.get_buffer(shape, dtype=np.float32)
    buffer[:] = 3.5
    pool.return_buffer(buffer)

    assert np.all(pool.get_buffer(shape, dtype=np.float32) == 0)


def test_distinct_dtypes_occupy_distinct_buckets(pool):
    """get_stats' available_buffer_types counts (shape, dtype) pairs now."""
    shape = (8,)
    for dtype in (np.float32, np.float64):
        pool.return_buffer(pool.get_buffer(shape, dtype=dtype))

    assert pool.get_stats()['available_buffer_types'] == 2
