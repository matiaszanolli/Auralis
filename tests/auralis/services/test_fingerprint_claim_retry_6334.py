"""A failed claim is retried, never read as "queue empty"; extraction failures never end a worker (#6334).

The scheduler's claim methods now raise on a database error. ``claim_with_retry`` rides
out a transient one and gives up only after ``CLAIM_FAILURE_LIMIT`` consecutive failures,
and the worker loop uses it for the claim only, so a streak of undecodable files cannot
count toward a worker leaving the pool.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from auralis.services import fingerprint_queue
from auralis.services.fingerprint_claim import (
    CLAIM_FAILURE_LIMIT,
    CLAIM_RETRY_MAX_SECONDS,
    claim_with_retry,
)
from auralis.services.fingerprint_queue import FingerprintExtractionQueue


def _locked() -> OperationalError:
    return OperationalError("SELECT", {}, Exception("database is locked"))


class TestClaimWithRetry:
    def test_an_empty_queue_is_returned_as_none_without_retrying(self):
        claim = MagicMock(return_value=None)
        sleep = MagicMock()

        assert claim_with_retry(claim, 0, lambda: False, sleep=sleep) is None

        claim.assert_called_once_with()
        sleep.assert_not_called()

    def test_one_transient_failure_is_ridden_out(self):
        track = SimpleNamespace(id=7)
        claim = MagicMock(side_effect=[_locked(), track])
        sleep = MagicMock()

        assert claim_with_retry(claim, 0, lambda: False, sleep=sleep) is track

        assert claim.call_count == 2
        sleep.assert_called_once()

    def test_persistent_failure_gives_up_after_the_limit_with_capped_backoff(self):
        claim = MagicMock(side_effect=_locked())
        sleep = MagicMock()

        assert claim_with_retry(claim, 0, lambda: False, sleep=sleep) is None

        assert claim.call_count == CLAIM_FAILURE_LIMIT
        pauses = [call.args[0] for call in sleep.call_args_list]
        assert len(pauses) == CLAIM_FAILURE_LIMIT - 1  # no pause after the last attempt
        assert pauses == sorted(pauses)  # backoff grows
        assert max(pauses) <= CLAIM_RETRY_MAX_SECONDS

    def test_a_stopping_pool_does_not_retry(self):
        claim = MagicMock(side_effect=_locked())
        sleep = MagicMock()

        assert claim_with_retry(claim, 0, lambda: True, sleep=sleep) is None

        claim.assert_called_once_with()
        sleep.assert_not_called()


def _queue(scheduler) -> FingerprintExtractionQueue:
    return FingerprintExtractionQueue(
        fingerprint_extractor=MagicMock(),
        get_repository_factory=lambda: SimpleNamespace(fingerprint_scheduler=scheduler),
        num_workers=1,
        enable_adaptive_scaling=False,
        max_workers=1,
        track_timeout=5,
    )


@pytest.fixture(autouse=True)
def _no_real_sleeps(monkeypatch):
    monkeypatch.setattr(fingerprint_queue.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr("auralis.services.fingerprint_claim.time.sleep", lambda _seconds: None)


class TestWorkerLoop:
    def test_a_worker_survives_a_transient_claim_error_and_keeps_processing(self):
        tracks = [SimpleNamespace(id=1, filepath="/a.flac"), SimpleNamespace(id=2, filepath="/b.flac")]
        scheduler = SimpleNamespace(
            claim_next_unfingerprinted_track=MagicMock(side_effect=[_locked(), tracks[0], tracks[1], None]),
            claim_next_outdated_fingerprint=MagicMock(side_effect=[_locked(), None]),
        )
        queue = _queue(scheduler)
        queue._process_track = MagicMock()  # type: ignore[method-assign]

        queue._worker_loop(0)

        assert [c.args[0].id for c in queue._process_track.call_args_list] == [1, 2]
        assert scheduler.claim_next_outdated_fingerprint.call_count == 2  # phase 2 ran after the error

    def test_a_streak_of_failing_extractions_does_not_end_the_worker(self):
        tracks = [SimpleNamespace(id=i, filepath=f"/{i}.flac") for i in range(CLAIM_FAILURE_LIMIT * 2)]
        scheduler = SimpleNamespace(
            claim_next_unfingerprinted_track=MagicMock(side_effect=[*tracks, None]),
            claim_next_outdated_fingerprint=MagicMock(return_value=None),
        )
        queue = _queue(scheduler)
        queue._process_track = MagicMock(side_effect=RuntimeError("undecodable"))  # type: ignore[method-assign]

        queue._worker_loop(0)

        assert queue._process_track.call_count == len(tracks)  # every track was still attempted

    def test_a_dead_database_ends_the_phase_instead_of_spinning(self):
        scheduler = SimpleNamespace(
            claim_next_unfingerprinted_track=MagicMock(side_effect=_locked()),
            claim_next_outdated_fingerprint=MagicMock(side_effect=_locked()),
        )
        queue = _queue(scheduler)
        queue._process_track = MagicMock()  # type: ignore[method-assign]

        queue._worker_loop(0)

        assert scheduler.claim_next_unfingerprinted_track.call_count == CLAIM_FAILURE_LIMIT
        assert scheduler.claim_next_outdated_fingerprint.call_count == CLAIM_FAILURE_LIMIT
        queue._process_track.assert_not_called()
