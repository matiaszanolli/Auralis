"""enqueue-all separates tracks the full queue dropped from tracks already pending (#5920).

enqueue() answers False for a duplicate, a track being processed and a full queue alike, and
the router counted every False as "already queued or processing", so on a library over
MAX_QUEUE_SIZE the overflow was silently reported as queued.
"""

from unittest.mock import MagicMock

from analysis.fingerprint_queue import FingerprintQueue


def _queue(max_size):
    queue = FingerprintQueue(MagicMock(), lambda track_id: None)
    queue.MAX_QUEUE_SIZE = max_size
    return queue


def test_overflow_is_dropped_not_already_pending():
    queue = _queue(3)

    assert queue.enqueue_many([1, 2, 3, 4, 5]) == (3, 0, 2)
    assert not queue.is_pending(4)


def test_duplicates_and_the_processing_track_are_already_pending():
    queue = _queue(10)
    queue.enqueue(1)
    queue._state.processing = 2

    assert queue.enqueue_many([1, 2, 3]) == (1, 2, 0)


def test_a_second_pass_after_the_queue_drains_takes_the_dropped_tracks():
    queue = _queue(2)
    assert queue.enqueue_many([1, 2, 3]) == (2, 0, 1)
    queue._state.queue.clear()
    queue._state.queued_set.clear()

    assert queue.enqueue_many([3]) == (1, 0, 0)
