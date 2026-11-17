"""on_drained fires only when every worker has finished BOTH phases (#6324)

Each worker used to report after Phase 1 and again after Phase 2, so a worker that finished both
phases counted twice while a slow one was still extracting, and the reference cloud was refreshed
from a half-fingerprinted library.
"""

import threading
from unittest.mock import MagicMock

from auralis.services.fingerprint_queue import FingerprintExtractionQueue


def _queue(workers: int) -> FingerprintExtractionQueue:
    queue = FingerprintExtractionQueue.__new__(FingerprintExtractionQueue)
    queue.workers = [MagicMock() for _ in range(workers)]
    queue.initial_num_workers = workers
    queue.should_stop = False
    queue._processed_since_drain = 1  # one track was fingerprinted in this wave
    queue._drained_workers = 0
    queue._drain_state_lock = threading.Lock()
    queue.on_drained = MagicMock()
    queue._claim = MagicMock(return_value=None)  # nothing left to claim in either phase
    return queue


def test_a_worker_finishing_both_phases_counts_once():
    queue = _queue(workers=2)

    queue._worker_loop(0)

    assert queue._drained_workers == 1
    queue.on_drained.assert_not_called()  # worker 1 has not finished, so the wave is not drained


def test_on_drained_fires_once_when_the_last_worker_finishes():
    queue = _queue(workers=2)

    queue._worker_loop(0)
    queue._worker_loop(1)

    queue.on_drained.assert_called_once()
    assert queue._drained_workers == 0  # reset for the next wave
