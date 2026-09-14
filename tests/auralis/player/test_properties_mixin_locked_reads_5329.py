"""Regression test: audio_data/reference_data getters read under _audio_lock (#5329).

Both properties' setters (and the sibling reference_file getter) already
acquired file_manager._audio_lock before this fix — the getters were the one
gap the class docstring's "every data-bearing property acquires its writer's
lock" rule didn't actually hold for. Harmless under the GIL today; a real
torn-read hazard under free-threaded Python 3.14 (PEP 703), which this
project targets.
"""

import threading

import numpy as np


class _TrackingRLock:
    """RLock wrapper that tracks acquisition depth (portable, no C internals).

    Same pattern as test_load_track_lock.py's _TrackingRLock.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self.depth = 0

    def __enter__(self):
        self._lock.__enter__()
        self.depth += 1
        return self

    def __exit__(self, *args):
        self.depth -= 1
        return self._lock.__exit__(*args)


class _FileManagerStub:
    """Stand-in whose data properties assert the lock is already held on read.

    This is a stronger check than "was __enter__ called at some point" — it
    fails if the property reads self._audio_data/_reference_data before (or
    after) actually holding the lock, not just if the lock was never touched.
    """
    def __init__(self, lock: _TrackingRLock):
        self._audio_lock = lock
        self._audio_data = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        self._reference_data = np.array([4.0, 5.0], dtype=np.float32)

    @property
    def audio_data(self):
        assert self._audio_lock.depth > 0, "audio_data read while _audio_lock was not held"
        return self._audio_data

    @audio_data.setter
    def audio_data(self, value):
        assert self._audio_lock.depth > 0, "audio_data write while _audio_lock was not held"
        self._audio_data = value

    @property
    def reference_data(self):
        assert self._audio_lock.depth > 0, "reference_data read while _audio_lock was not held"
        return self._reference_data

    @reference_data.setter
    def reference_data(self, value):
        assert self._audio_lock.depth > 0, "reference_data write while _audio_lock was not held"
        self._reference_data = value


def _make_player():
    from auralis.player.enhanced_audio_player import AudioPlayer

    player = AudioPlayer.__new__(AudioPlayer)
    lock = _TrackingRLock()
    player.file_manager = _FileManagerStub(lock)
    return player, lock


def test_audio_data_getter_holds_lock_during_read():
    """The stub's property raises AssertionError if read without the lock held."""
    player, lock = _make_player()
    result = player.audio_data
    np.testing.assert_array_equal(result, [1.0, 2.0, 3.0])
    assert lock.depth == 0, "lock must be released after the read completes"


def test_reference_data_getter_holds_lock_during_read():
    player, lock = _make_player()
    result = player.reference_data
    np.testing.assert_array_equal(result, [4.0, 5.0])
    assert lock.depth == 0, "lock must be released after the read completes"


def test_audio_data_getter_and_setter_use_the_same_lock():
    """Getter and setter must guard with the identical lock object (not
    separate locks that happen to both be named _audio_lock)."""
    player, lock = _make_player()
    new_data = np.zeros(4, dtype=np.float32)

    player.audio_data = new_data  # setter — also asserts lock held, via the stub
    np.testing.assert_array_equal(player.audio_data, new_data)  # getter
    assert lock.depth == 0


def test_reference_data_getter_and_setter_use_the_same_lock():
    player, lock = _make_player()
    new_data = np.ones(4, dtype=np.float32)

    player.reference_data = new_data
    np.testing.assert_array_equal(player.reference_data, new_data)
    assert lock.depth == 0


def test_no_regression_for_plain_unlocked_access_pattern():
    """A caller that just reads audio_data/reference_data with no concurrency
    involved must still get back exactly what was stored — the lock is a
    correctness hardening with no functional/value change (issue's own
    acceptance criterion)."""
    player, _lock = _make_player()

    np.testing.assert_array_equal(player.audio_data, [1.0, 2.0, 3.0])
    np.testing.assert_array_equal(player.reference_data, [4.0, 5.0])
