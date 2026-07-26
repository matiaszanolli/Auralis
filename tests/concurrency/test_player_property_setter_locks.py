"""
Regression tests for PlayerPropertiesMixin setter lock discipline (#4574)

The three "compatibility" setters — ``current_track``, ``reference_data``,
``sample_rate`` — used to write straight through to the underlying manager
without taking the lock their readers hold, while their neighbour
``audio_data`` did (#3443). Under a free-threaded build that lets a reader
observe a half-updated composite (a new ``sample_rate`` paired with the old
``audio_data``, or a ``current_track`` inconsistent with the position snapshot
``_position_lock`` exists to make atomic).

Covers:
- Each setter acquires the lock its readers use
- No direct ``integration.current_track = ...`` assignment remains
- ``(sample_rate, audio_data)`` composites are never observed mixed
- ``position`` stays on AudioPlayer, not the mixin (#4574 acceptance criteria)
"""

import inspect
import threading
from unittest.mock import MagicMock

import numpy as np
import pytest

from auralis.player.audio_file_manager import AudioFileManager
from auralis.player.integration_manager import IntegrationManager
from auralis.player.playback_controller import PlaybackController
from auralis.player.player_properties_mixin import PlayerPropertiesMixin


class RecordingLock:
    """RLock wrapper that counts acquisitions and tracks live ownership."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.acquire_count = 0
        self.held = False

    def __enter__(self) -> "RecordingLock":
        self._lock.acquire()
        self.acquire_count += 1
        self.held = True
        return self

    def __exit__(self, *exc: object) -> None:
        self.held = False
        self._lock.release()

    def acquire(self, *args: object, **kwargs: object) -> bool:
        result = self._lock.acquire(*args, **kwargs)  # type: ignore[arg-type]
        if result:
            self.acquire_count += 1
            self.held = True
        return result

    def release(self) -> None:
        self.held = False
        self._lock.release()


def _make_integration() -> IntegrationManager:
    """Build a real IntegrationManager with cheap collaborators."""
    return IntegrationManager(
        playback=PlaybackController(),
        file_manager=AudioFileManager(),
        queue=MagicMock(),
        processor=MagicMock(),
        get_repository_factory=lambda: MagicMock(),
    )


class _Player(PlayerPropertiesMixin):
    """Minimal host for the mixin — mirrors what AudioPlayer.__init__ sets."""

    def __init__(self) -> None:
        self.file_manager = AudioFileManager()
        self.integration = _make_integration()


@pytest.fixture
def player() -> _Player:
    p = _Player()
    p.file_manager._audio_lock = RecordingLock()  # type: ignore[assignment]
    p.integration._position_lock = RecordingLock()  # type: ignore[assignment]
    return p


class TestSetterAcquiresReaderLock:
    """Each data-bearing setter takes the lock its readers hold."""

    def test_sample_rate_setter_takes_audio_lock(self, player):
        player.sample_rate = 48000

        assert player.file_manager._audio_lock.acquire_count == 1
        assert player.sample_rate == 48000

    def test_reference_data_setter_takes_audio_lock(self, player):
        data = np.zeros((100, 2), dtype=np.float32)
        player.reference_data = data

        assert player.file_manager._audio_lock.acquire_count == 1
        assert player.reference_data is data

    def test_audio_data_setter_takes_audio_lock(self, player):
        """The already-correct neighbour (#3443) — guards against regression."""
        player.audio_data = np.zeros((100, 2), dtype=np.float32)

        assert player.file_manager._audio_lock.acquire_count == 1

    def test_current_track_setter_takes_position_lock(self, player):
        track = object()
        player.current_track = track

        assert player.integration._position_lock.acquire_count == 1
        assert player.current_track is track

    def test_integration_owns_the_current_track_lock(self):
        """The mixin delegates rather than reaching into another object's lock."""
        integration = _make_integration()
        integration._position_lock = RecordingLock()  # type: ignore[assignment]

        track = object()
        integration.set_current_track(track)

        assert integration._position_lock.acquire_count == 1
        assert integration.current_track is track


class TestNoUnlockedBypass:
    """White-box: keep the four setters from drifting apart again."""

    @pytest.mark.parametrize(
        "prop,expected",
        [
            ("audio_data", "_audio_lock"),
            ("reference_data", "_audio_lock"),
            ("sample_rate", "_audio_lock"),
            ("current_track", "set_current_track"),
        ],
    )
    def test_setter_body_references_its_guard(self, prop, expected):
        setter = PlayerPropertiesMixin.__dict__[prop].fset
        assert setter is not None, f"{prop} setter should exist"
        assert expected in inspect.getsource(setter), (
            f"{prop} setter must go through {expected} — writing through "
            f"unguarded bypasses the lock its readers hold (#4574)"
        )

    def test_set_current_track_holds_position_lock(self):
        src = inspect.getsource(IntegrationManager.set_current_track)
        assert "with self._position_lock:" in src

    def test_no_direct_integration_current_track_assignment(self):
        """`grep -rn "integration.current_track"` must show no assignment."""
        import auralis.player.player_properties_mixin as mixin_mod

        assert "self.integration.current_track =" not in inspect.getsource(mixin_mod)

    def test_position_stays_on_audio_player(self):
        """`position` must NOT migrate into this mixin (#4574 acceptance)."""
        from auralis.player.enhanced_audio_player import AudioPlayer

        assert "position" not in PlayerPropertiesMixin.__dict__
        assert "position" in AudioPlayer.__dict__


class TestCompositeConsistency:
    """A reader never sees a sample_rate/audio_data pair from two writers."""

    def test_sample_rate_and_audio_data_stay_consistent(self, player):
        # Two valid composites; a mix of the two proves a torn read.
        pairs = {(44100, 100), (48000, 200)}
        observed: list[tuple[int, int]] = []
        stop = threading.Event()
        errors: list[BaseException] = []

        def writer() -> None:
            try:
                for i in range(300):
                    sr, n = (44100, 100) if i % 2 == 0 else (48000, 200)
                    with player.file_manager._audio_lock:
                        player.sample_rate = sr
                        player.audio_data = np.zeros((n, 2), dtype=np.float32)
            except BaseException as exc:  # pragma: no cover - diagnostic
                errors.append(exc)
            finally:
                stop.set()

        def reader() -> None:
            try:
                while not stop.is_set():
                    with player.file_manager._audio_lock:
                        data = player.audio_data
                        if data is not None:
                            observed.append((player.sample_rate, len(data)))
            except BaseException as exc:  # pragma: no cover - diagnostic
                errors.append(exc)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"threads raised: {errors}"
        assert observed, "reader never sampled a composite"
        assert set(observed) <= pairs, (
            f"observed torn composite(s): {set(observed) - pairs}"
        )
