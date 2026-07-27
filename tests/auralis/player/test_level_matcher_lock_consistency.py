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
from pathlib import Path

import numpy as np

# Repo-relative, not an absolute developer path: hardcoding
# "/mnt/data/src/matchering" made this file import `auralis` from that checkout
# no matter where the tests ran, so a git-worktree baseline comparison silently
# exercised the *working* tree and reported green for an unfixed HEAD.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

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


class TestGetStatsTakesTheLock:
    """#4551 — the reader half of #4340.

    get_stats() read four pieces of mutable state with no lock while every
    writer mutated them under _lock. reset() rebinds gain_smoother while
    holding the lock, so the two gain reads could straddle the swap.
    """

    def test_get_stats_acquires_lock_exactly_once(self):
        matcher = RealtimeLevelMatcher(_config())
        acquisitions = []
        real_lock = matcher._lock

        class CountingLock:
            def __enter__(self):
                acquisitions.append(1)
                return real_lock.__enter__()

            def __exit__(self, *exc):
                return real_lock.__exit__(*exc)

        matcher._lock = CountingLock()
        matcher.get_stats()

        assert sum(acquisitions) == 1, "get_stats must take _lock exactly once"

    def test_gain_values_come_from_one_smoother_instance(self):
        """current_gain/target_gain must never be paired across a reset()."""
        matcher = RealtimeLevelMatcher(_config())
        reference = np.random.uniform(-0.5, 0.5, (44100, 2)).astype(np.float32)
        matcher.set_reference_audio(reference)

        stop = threading.Event()
        errors: list[BaseException] = []
        observations: list[dict] = []

        def _reset_thread():
            while not stop.is_set():
                try:
                    matcher.reset()
                    matcher.set_reference_audio(reference)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        def _stats_thread():
            for _ in range(500):
                try:
                    observations.append(matcher.get_stats())
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
                    return

        reset_t = threading.Thread(target=_reset_thread)
        stats_t = threading.Thread(target=_stats_thread)
        reset_t.start()
        stats_t.start()
        stats_t.join(timeout=10)
        stop.set()
        reset_t.join(timeout=10)

        assert not errors, f"concurrent get_stats raised: {errors}"
        assert observations

        # A freshly-reset smoother has both gains at their initial value. Any
        # dict pairing a post-reset current_gain with a pre-reset target_gain
        # (or vice versa) would show up as a self-inconsistent snapshot: when
        # the matcher reports itself disabled with no reference, the gains must
        # be those of the new smoother, not leftovers from the old one.
        for stats in observations:
            if stats['enabled'] is False and stats['reference_loaded'] is False:
                assert stats['current_gain'] == stats['target_gain'], (
                    f"torn read across reset(): {stats}"
                )

    def test_sibling_get_stats_implementations_both_lock(self):
        """Keeps RealtimeLevelMatcher and AutoMasterProcessor from drifting.

        A white-box guard: both classes' get_stats must reference their lock,
        so a future edit that drops one is caught here rather than in
        production telemetry.
        """
        import inspect

        from auralis.player.realtime.auto_master import AutoMasterProcessor

        for cls in (RealtimeLevelMatcher, AutoMasterProcessor):
            source = inspect.getsource(cls.get_stats)
            assert 'self._lock' in source, (
                f"{cls.__name__}.get_stats must acquire self._lock (#4551)"
            )


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
