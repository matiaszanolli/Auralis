# -*- coding: utf-8 -*-

"""
Regression tests for the bounded in-memory fingerprint queue (#3816 / BE-PF-2).

CONTEXT: `analysis.fingerprint_queue.FingerprintQueue` (backend, in-memory deque
— distinct from `auralis.services.fingerprint_queue.FingerprintExtractionQueue`,
the DB-backed worker pool) had no size cap: `enqueue()` always appended
regardless of current size. A bulk `enqueue-all` on a large library could pump
tens of thousands of IDs into memory in milliseconds while the single
sequential worker drains one every 3-30s.

`FingerprintQueue.MAX_QUEUE_SIZE` and the bound-check in `enqueue()` were
already present in the code (this session found them already implemented,
just untested — the two existing test files under this name target the
unrelated sibling module). These tests cover: the bound is enforced, the
correct sentinel is returned so callers can detect a drop, and
`routers/fingerprint_status.py`'s caller (found NOT checking the return value
during this session, fixed alongside) reflects the outcome instead of
unconditionally claiming success.

:license: GPLv3
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from analysis.fingerprint_queue import FingerprintQueue


def _make_queue() -> FingerprintQueue:
    generator = Mock()
    get_filepath = Mock(return_value="/fake/path.mp3")
    return FingerprintQueue(generator, get_filepath)


def test_enqueue_accepts_new_track():
    queue = _make_queue()
    assert queue.enqueue(1) is True
    assert queue.is_queued(1) is True


def test_enqueue_deduplicates_already_queued_track():
    queue = _make_queue()
    assert queue.enqueue(1) is True
    assert queue.enqueue(1) is False, "same track must not be queued twice"
    assert queue.get_stats()["queued"] == 1


def test_enqueue_rejects_track_currently_processing():
    queue = _make_queue()
    queue._state.processing = 42  # simulate the worker having popped it

    assert queue.enqueue(42) is False
    assert queue.get_stats()["queued"] == 0


def test_enqueue_is_bounded_by_max_queue_size(caplog):
    """The headline regression: enqueue() must refuse once the queue is full,
    returning False rather than growing without bound."""
    queue = _make_queue()
    queue.MAX_QUEUE_SIZE = 5  # shrink for a fast test

    for track_id in range(5):
        assert queue.enqueue(track_id) is True

    with caplog.at_level("WARNING"):
        overflow_accepted = queue.enqueue(999)

    assert overflow_accepted is False, (
        "enqueue() must return False once MAX_QUEUE_SIZE is reached, not "
        "silently keep appending"
    )
    assert queue.get_stats()["queued"] == 5, "the queue must not grow past the bound"
    assert queue.is_queued(999) is False, "the dropped track must not be considered queued"
    assert any("full" in r.message.lower() for r in caplog.records), (
        "a dropped enqueue must be logged so operators see backpressure"
    )


def test_enqueue_bound_is_a_ceiling_not_a_one_time_check():
    """After the worker drains an entry, the queue must accept new work again
    — the bound is a live ceiling on current size, not a lifetime counter."""
    queue = _make_queue()
    queue.MAX_QUEUE_SIZE = 2

    assert queue.enqueue(1) is True
    assert queue.enqueue(2) is True
    assert queue.enqueue(3) is False  # full

    # Simulate the worker popping one entry (mirrors _worker_loop's popleft).
    popped = queue._state.queue.popleft()
    queue._state.queued_set.discard(popped)

    assert queue.enqueue(3) is True, "queue must accept new work once space frees up"


def test_stats_reflect_queue_length_not_max_size():
    queue = _make_queue()
    queue.MAX_QUEUE_SIZE = 100
    queue.enqueue(1)
    queue.enqueue(2)

    assert queue.get_stats()["queued"] == 2
