"""Regression tests for the RealtimeProcessor/RealtimeLevelMatcher lock mismatch (#4340).

RealtimeProcessor.set_effect_enabled and reset_all_effects used to write
level_matcher.enabled / reference_rms / gain_smoother as raw attributes while
holding RealtimeProcessor.lock, but RealtimeLevelMatcher.process() reads
those same fields under RealtimeLevelMatcher._lock — two different mutexes
guarding one piece of state, so the paths did not serialize. Mutations now
go through RealtimeLevelMatcher.set_enabled()/reset(), which acquire the
matcher's own lock, mirroring AutoMasterProcessor's already-safe pattern.
"""

import sys
import threading

import numpy as np

sys.path.insert(0, "/mnt/data/src/matchering")

from auralis.player.config import PlayerConfig
from auralis.player.realtime.level_matcher import RealtimeLevelMatcher
from auralis.player.realtime.processor import RealtimeProcessor


def _config() -> PlayerConfig:
    config = PlayerConfig()
    config.sample_rate = 44100
    config.buffer_size = 512
    config.enable_level_matching = True
    config.enable_auto_mastering = False
    return config


class TestLevelMatcherLockedMutators:
    def test_set_enabled_acquires_lock(self):
        matcher = RealtimeLevelMatcher(_config())
        matcher.set_enabled(True)
        assert matcher.enabled is True
        matcher.set_enabled(False)
        assert matcher.enabled is False

    def test_reset_clears_reference_and_gain_smoother(self):
        matcher = RealtimeLevelMatcher(_config())
        reference = np.random.uniform(-0.5, 0.5, (44100, 2)).astype(np.float32)
        matcher.set_reference_audio(reference)
        assert matcher.reference_rms is not None
        assert matcher.enabled is True

        original_smoother = matcher.gain_smoother
        matcher.reset()

        assert matcher.reference_rms is None
        assert matcher.enabled is False
        assert matcher.gain_smoother is not original_smoother


class TestProcessorRoutesThroughLockedAPI:
    def test_set_effect_enabled_uses_locked_setter(self):
        processor = RealtimeProcessor(_config())
        processor.set_effect_enabled('level_matching', True)
        assert processor.level_matcher.enabled is True

        processor.set_effect_enabled('level_matching', False)
        assert processor.level_matcher.enabled is False

    def test_reset_all_effects_resets_level_matcher_state(self):
        processor = RealtimeProcessor(_config())
        reference = np.random.uniform(-0.5, 0.5, (44100, 2)).astype(np.float32)
        processor.set_reference_audio(reference)
        assert processor.level_matcher.reference_rms is not None

        processor.reset_all_effects()

        assert processor.level_matcher.reference_rms is None
        assert processor.level_matcher.enabled is False
        assert processor.effects_enabled['level_matching'] is False


class TestConcurrentMutationDuringProcessing:
    """Mirrors the issue's test plan: concurrently run process() and the
    mutators; assert no exception and no partially-applied state (enabled
    True with reference_rms mismatch)."""

    def test_concurrent_set_effect_enabled_and_process_no_exception(self):
        processor = RealtimeProcessor(_config())
        reference = np.random.uniform(-0.5, 0.5, (44100, 2)).astype(np.float32)
        processor.set_reference_audio(reference)

        chunk = np.random.uniform(-0.3, 0.3, (512, 2)).astype(np.float32)
        stop = threading.Event()
        errors: list[BaseException] = []

        def _audio_thread():
            while not stop.is_set():
                try:
                    processor.level_matcher.process(chunk)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        def _control_thread():
            for i in range(200):
                try:
                    processor.set_effect_enabled('level_matching', i % 2 == 0)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        audio_t = threading.Thread(target=_audio_thread)
        control_t = threading.Thread(target=_control_thread)
        audio_t.start()
        control_t.start()
        control_t.join(timeout=10)
        stop.set()
        audio_t.join(timeout=10)

        assert not errors, f"concurrent access raised: {errors}"

    def test_concurrent_reset_and_process_no_exception(self):
        processor = RealtimeProcessor(_config())
        reference = np.random.uniform(-0.5, 0.5, (44100, 2)).astype(np.float32)
        processor.set_reference_audio(reference)

        chunk = np.random.uniform(-0.3, 0.3, (512, 2)).astype(np.float32)
        stop = threading.Event()
        errors: list[BaseException] = []

        def _audio_thread():
            while not stop.is_set():
                try:
                    processor.level_matcher.process(chunk)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        def _reset_thread():
            for _ in range(100):
                try:
                    processor.reset_all_effects()
                    processor.set_reference_audio(reference)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        audio_t = threading.Thread(target=_audio_thread)
        reset_t = threading.Thread(target=_reset_thread)
        audio_t.start()
        reset_t.start()
        reset_t.join(timeout=10)
        stop.set()
        audio_t.join(timeout=10)

        assert not errors, f"concurrent access raised: {errors}"
