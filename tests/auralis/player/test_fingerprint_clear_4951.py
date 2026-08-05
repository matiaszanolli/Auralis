"""Regression tests for clearing stale adaptive fingerprint state (#4951)."""

import threading
from unittest.mock import MagicMock

import pytest

from auralis.player.config import PlayerConfig
from auralis.player.fingerprint_loader_mixin import PlayerFingerprintLoaderMixin
from auralis.player.realtime.auto_master import AutoMasterProcessor
from auralis.player.realtime.processor import RealtimeProcessor

FINGERPRINT = {
    "lufs": -18.0,
    "crest_db": 15.0,
    "bass_pct": 0.2,
    "transient_density": 0.4,
}


def _config() -> PlayerConfig:
    return PlayerConfig(enable_level_matching=False, enable_auto_mastering=True)


def test_auto_master_clear_fingerprint_resets_all_adaptive_state():
    processor = AutoMasterProcessor(_config())
    processor.set_fingerprint(FINGERPRINT)

    processor.clear_fingerprint()

    assert processor.fingerprint is None
    assert processor.adaptive_params is None


def test_realtime_processor_none_clears_auto_master_fingerprint():
    processor = RealtimeProcessor(_config())
    processor.set_fingerprint(FINGERPRINT)

    processor.set_fingerprint(None)

    assert processor.auto_master is not None
    assert processor.auto_master.fingerprint is None
    assert processor.auto_master.adaptive_params is None


@pytest.mark.parametrize("failure", [None, RuntimeError("fingerprint failed")])
def test_loader_failure_paths_clear_previous_track_state(failure):
    loader = PlayerFingerprintLoaderMixin()
    loader.fingerprint_service = MagicMock()
    if failure is None:
        loader.fingerprint_service.get_or_compute.return_value = None
    else:
        loader.fingerprint_service.get_or_compute.side_effect = failure

    loader.processor = RealtimeProcessor(_config())
    loader.processor.set_fingerprint(FINGERPRINT)
    loader._current_fingerprint = FINGERPRINT
    loader._fingerprint_lock = threading.Lock()
    loader._track_generation = 7

    loader._load_fingerprint_for_file("/tmp/missing.wav", generation=7)

    assert loader._current_fingerprint is None
    assert loader.processor.auto_master is not None
    assert loader.processor.auto_master.fingerprint is None
    assert loader.processor.auto_master.adaptive_params is None
