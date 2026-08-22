"""
Direct isolation tests for ``PlayerFingerprintLoaderMixin`` (#4249).

``test_fingerprint_clear_4951.py`` already covers the failure/None paths of
``_load_fingerprint_for_file`` in isolation. This file rounds out the
"start / cancel" behavior called for by #4249's test plan: the mixin has no
literal stop()/cancel() method — background loads are cancelled implicitly
by generation mismatch — so these tests exercise that contract directly
against a bare ``PlayerFingerprintLoaderMixin()`` instance, with no
``AudioPlayer`` construction involved.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from unittest.mock import MagicMock

from auralis.player.config import PlayerConfig
from auralis.player.fingerprint_loader_mixin import PlayerFingerprintLoaderMixin
from auralis.player.realtime.processor import RealtimeProcessor

FINGERPRINT = {
    "lufs": -14.0,
    "crest_db": 12.0,
    "bass_pct": 0.3,
    "transient_density": 0.5,
}


def _loader() -> PlayerFingerprintLoaderMixin:
    """A bare mixin instance with just the state it declares needing."""
    loader = PlayerFingerprintLoaderMixin()
    loader.fingerprint_service = MagicMock()
    loader.processor = RealtimeProcessor(
        PlayerConfig(enable_level_matching=False, enable_auto_mastering=True)
    )
    loader._current_fingerprint = None
    loader._fingerprint_lock = threading.Lock()
    loader._track_generation = 0
    return loader


def _wait_for(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate(), "condition did not become true within timeout"


class TestScheduleStartsBackgroundLoad:
    """`_schedule_fingerprint_load` is the mixin's "start" operation."""

    def test_bumps_generation_and_spawns_daemon_thread(self) -> None:
        loader = _loader()
        loader.fingerprint_service.get_or_compute.return_value = FINGERPRINT

        before = loader._track_generation
        loader._schedule_fingerprint_load("/tmp/track.flac")

        assert loader._track_generation == before + 1

        _wait_for(lambda: loader._current_fingerprint is not None)
        assert loader._current_fingerprint == FINGERPRINT
        loader.fingerprint_service.get_or_compute.assert_called_once()

    def test_each_call_gets_a_distinct_incrementing_generation(self) -> None:
        loader = _loader()
        loader.fingerprint_service.get_or_compute.return_value = None

        loader._schedule_fingerprint_load("/tmp/a.flac")
        loader._schedule_fingerprint_load("/tmp/b.flac")
        loader._schedule_fingerprint_load("/tmp/c.flac")

        assert loader._track_generation == 3


class TestLoadAppliesFingerprintToProcessor:
    """Success path of the "start" operation's background work."""

    def test_found_fingerprint_is_applied_to_processor(self) -> None:
        loader = _loader()
        loader.fingerprint_service.get_or_compute.return_value = FINGERPRINT
        loader._track_generation = 1

        loader._load_fingerprint_for_file("/tmp/track.flac", generation=1)

        assert loader._current_fingerprint == FINGERPRINT
        assert loader.processor.auto_master is not None
        assert loader.processor.auto_master.fingerprint == FINGERPRINT


class TestStaleGenerationIsCancelled:
    """No explicit cancel() exists — a superseding load discards the older
    one via the generation check, which is this mixin's cancellation
    mechanism (#3445, #3473, #3719)."""

    def test_stale_generation_result_is_discarded(self) -> None:
        loader = _loader()
        loader.fingerprint_service.get_or_compute.return_value = FINGERPRINT
        # Simulate a newer load having already started (and bumped the
        # generation) while this in-flight call's result comes back late.
        loader._track_generation = 5

        loader._load_fingerprint_for_file("/tmp/stale.flac", generation=3)

        assert loader._current_fingerprint is None
        assert loader.processor.auto_master is None or loader.processor.auto_master.fingerprint is None

    def test_newer_schedule_supersedes_older_in_flight_generation(self) -> None:
        """End-to-end through `_schedule_fingerprint_load`: scheduling a
        second load bumps the generation so the first, if it were to land
        after, would be discarded by the guard above. This asserts the
        publicly observable half of that contract — the counter moves."""
        loader = _loader()
        loader.fingerprint_service.get_or_compute.return_value = FINGERPRINT

        loader._schedule_fingerprint_load("/tmp/first.flac")
        _wait_for(lambda: loader._track_generation >= 1)
        gen_after_first = loader._track_generation

        loader._schedule_fingerprint_load("/tmp/second.flac")
        _wait_for(lambda: loader._track_generation > gen_after_first)

        assert loader._track_generation == gen_after_first + 1


class TestLoadErrorClearsFingerprint:
    def test_exception_during_compute_clears_current_fingerprint(self) -> None:
        loader = _loader()
        loader._current_fingerprint = FINGERPRINT
        loader.processor.set_fingerprint(FINGERPRINT)
        loader.fingerprint_service.get_or_compute.side_effect = RuntimeError("boom")
        loader._track_generation = 2

        loader._load_fingerprint_for_file("/tmp/broken.flac", generation=2)

        assert loader._current_fingerprint is None
        assert loader.processor.auto_master is not None
        assert loader.processor.auto_master.fingerprint is None
