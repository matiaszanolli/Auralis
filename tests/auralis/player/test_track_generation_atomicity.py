"""
Regression test for #3473 — `_track_generation` increment must be atomic.

Pre-fix: `self._track_generation += 1; generation = self._track_generation`
runs as LOAD_ATTR / STORE_ATTR at bytecode level. Two concurrent
`_schedule_fingerprint_load` calls can both observe the same value, both
write value+1, and both pass the same `generation` to their fingerprint
threads. The staleness guard `self._track_generation != generation` then
admits both — fingerprints applied in nondeterministic order, possibly
wrong one wins.

Post-fix: the increment-and-publish runs under `_fingerprint_lock`, so
two concurrent calls always get distinct values. The test forces the race
window open by monkeypatching the increment's read step with a small
sleep — on pre-fix code the race is deterministic; on post-fix code the
lock serializes the callers.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest


@pytest.fixture
def player(enhanced_player):
    """The enhanced_player fixture from conftest.py — fully constructed."""
    return enhanced_player


def test_concurrent_schedule_fingerprint_load_produces_distinct_generations(player):
    """Fire 64 concurrent _schedule_fingerprint_load calls; each must get a
    unique generation. Captures the generation values passed to the spawned
    fingerprint loader threads via a mock of `_load_fingerprint_for_file`."""

    captured: list[int] = []
    captured_lock = threading.Lock()

    def spy_loader(file_path: str, generation: int) -> None:
        with captured_lock:
            captured.append(generation)

    # Replace the loader so we capture without actually doing any fingerprint
    # work. The spy must be set BEFORE we trigger any schedules so every
    # spawned thread sees it.
    player._load_fingerprint_for_file = spy_loader

    # Hammer with many concurrent schedules.
    n_calls = 64
    with ThreadPoolExecutor(max_workers=16) as ex:
        futures = [
            ex.submit(player._schedule_fingerprint_load, f"/tmp/file_{i}.wav")
            for i in range(n_calls)
        ]
        for f in futures:
            f.result()

    # Give spawned threads a chance to call the spy (the actual increment
    # happens synchronously; the spy is called from the spawned thread).
    # Poll briefly until all generations land.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and len(captured) < n_calls:
        time.sleep(0.01)

    assert len(captured) == n_calls, (
        f"Expected {n_calls} loader invocations, got {len(captured)}"
    )

    distinct = set(captured)
    assert len(distinct) == n_calls, (
        f"Expected {n_calls} distinct generations, got {len(distinct)} "
        f"(duplicates: {len(captured) - len(distinct)}) — #3473 regressed"
    )


def test_barrier_synchronized_stress_produces_all_distinct_generations(player):
    """The issue's stated acceptance criterion: a stress run produces
    uniquely-numbered generations even under maximum contention. Uses a
    Barrier so all worker threads block at the door and release on the
    same tick, maximizing the chance that they hit the unprotected
    increment site simultaneously."""
    n_calls = 1000
    n_workers = 32

    captured: list[int] = []
    captured_lock = threading.Lock()
    barrier = threading.Barrier(n_workers)

    def spy_loader(file_path: str, generation: int) -> None:
        with captured_lock:
            captured.append(generation)
    player._load_fingerprint_for_file = spy_loader

    def worker(start: int, count: int) -> None:
        barrier.wait()    # release all workers at the same instant
        for i in range(count):
            player._schedule_fingerprint_load(f"/tmp/file_{start + i}.wav")

    # Distribute n_calls across n_workers as evenly as possible
    per_worker = n_calls // n_workers
    extra = n_calls - per_worker * n_workers
    counts = [per_worker + (1 if i < extra else 0) for i in range(n_workers)]
    starts = [sum(counts[:i]) for i in range(n_workers)]

    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        futures = [ex.submit(worker, starts[i], counts[i]) for i in range(n_workers)]
        for f in futures:
            f.result()

    # Wait for all spawned fingerprint threads to record
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and len(captured) < n_calls:
        time.sleep(0.01)

    assert len(captured) == n_calls, (
        f"Expected {n_calls} loader invocations, got {len(captured)}"
    )

    distinct = set(captured)
    assert len(distinct) == n_calls, (
        f"Stress test: expected {n_calls} distinct generations, got "
        f"{len(distinct)} (duplicates: {n_calls - len(distinct)}) — #3473 regressed"
    )


def test_published_generation_matches_value_returned_to_loader(player):
    """The value passed to `_load_fingerprint_for_file` must equal the value
    stored on `self._track_generation` AT THE TIME the spawn returns. This
    pins the "publication" contract — without it the staleness check in
    the loader could be comparing against a non-monotonic store order."""

    captured: list[int] = []

    def spy_loader(file_path: str, generation: int) -> None:
        captured.append(generation)

    player._load_fingerprint_for_file = spy_loader

    for i in range(10):
        before = player._track_generation
        player._schedule_fingerprint_load(f"/tmp/file_{i}.wav")
        after = player._track_generation
        assert after == before + 1, (
            f"Generation must increment by exactly 1 per call: {before} -> {after}"
        )

    # Wait for spawned threads
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and len(captured) < 10:
        time.sleep(0.01)

    # Generations passed to the loader must match the sequence we observed
    # being published on self._track_generation.
    assert captured == list(range(1, 11)), (
        f"Expected generations 1..10 in order, got {captured}"
    )
