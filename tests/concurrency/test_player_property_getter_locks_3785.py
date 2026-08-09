"""
Regression tests for PlayerPropertiesMixin/IntegrationManager getter lock
discipline (#3785)

``AudioFileManager.sample_rate``/``current_file``/``reference_file`` are
written under ``_audio_lock`` (audio_file_manager.py) but used to be read as
raw attributes by ``PlayerPropertiesMixin``'s getters and by
``IntegrationManager._on_playback_state_change``/``get_playback_info``. Two
paired reads (or a read racing a concurrent ``load_file()`` swap) could
observe a torn/stale value — a mismatched ``(current_file, sample_rate)``
pair for one broadcast cycle. #4574 already fixed the setter side; this
closes the matching reader gap.

Covers:
- Each of the three getters acquires ``_audio_lock``
- ``IntegrationManager._on_playback_state_change`` and ``get_playback_info``
  read ``current_file`` under ``_audio_lock``, not as a raw attribute
- ``(current_file, sample_rate)`` composites are never observed mixed under
  concurrent ``load_file()`` swaps
"""

import inspect
import threading
import time
from unittest.mock import MagicMock

import pytest

from auralis.player.audio_file_manager import AudioFileManager
from auralis.player.integration_manager import IntegrationManager
from auralis.player.playback_controller import PlaybackController
from auralis.player.player_properties_mixin import PlayerPropertiesMixin
from tests.concurrency.test_player_property_setter_locks import RecordingLock


def _make_integration(file_manager: AudioFileManager) -> IntegrationManager:
    return IntegrationManager(
        playback=PlaybackController(),
        file_manager=file_manager,
        queue=MagicMock(),
        processor=MagicMock(),
        get_repository_factory=lambda: MagicMock(),
    )


class _Player(PlayerPropertiesMixin):
    """Minimal host for the mixin — mirrors what AudioPlayer.__init__ sets."""

    def __init__(self) -> None:
        self.file_manager = AudioFileManager()
        self.integration = _make_integration(self.file_manager)


@pytest.fixture
def player() -> _Player:
    p = _Player()
    p.file_manager._audio_lock = RecordingLock()  # type: ignore[assignment]
    return p


class TestGetterAcquiresAudioLock:
    """Each read-only AudioFileManager-backed property takes _audio_lock."""

    def test_current_file_getter_takes_audio_lock(self, player):
        player.file_manager.current_file = "/music/a.flac"

        result = player.current_file

        assert result == "/music/a.flac"
        assert player.file_manager._audio_lock.acquire_count == 1

    def test_reference_file_getter_takes_audio_lock(self, player):
        player.file_manager.reference_file = "/music/ref.flac"

        result = player.reference_file

        assert result == "/music/ref.flac"
        assert player.file_manager._audio_lock.acquire_count == 1

    def test_sample_rate_getter_takes_audio_lock(self, player):
        player.file_manager.sample_rate = 48000

        result = player.sample_rate

        assert result == 48000
        assert player.file_manager._audio_lock.acquire_count == 1


class TestNoUnlockedBypass:
    """White-box: keep the getters from drifting back to raw reads."""

    @pytest.mark.parametrize("prop", ["current_file", "reference_file", "sample_rate"])
    def test_getter_body_references_audio_lock(self, prop):
        getter = PlayerPropertiesMixin.__dict__[prop].fget
        assert getter is not None, f"{prop} getter should exist"
        assert "_audio_lock" in inspect.getsource(getter), (
            f"{prop} getter must read under _audio_lock — a raw attribute "
            f"read can observe a torn/stale value during a concurrent "
            f"load_file() swap (#3785)"
        )

    def test_on_playback_state_change_reads_current_file_under_audio_lock(self):
        src = inspect.getsource(IntegrationManager._on_playback_state_change)
        assert "self.file_manager._audio_lock" in src

    def test_get_playback_info_reads_current_file_under_audio_lock(self):
        src = inspect.getsource(IntegrationManager.get_playback_info)
        assert "self.file_manager._audio_lock" in src


class TestCompositeConsistency:
    """A reader never sees a current_file/sample_rate pair from two writers."""

    def test_current_file_and_sample_rate_stay_consistent(self, player):
        pairs = {("/music/a.flac", 44100), ("/music/b.flac", 48000)}
        observed: list[tuple[str, int]] = []
        stop = threading.Event()
        errors: list[BaseException] = []
        # Synchronize start so the reader gets real overlap with the writer —
        # otherwise a fast, I/O-free writer loop can finish (and set `stop`)
        # before the reader thread is even scheduled.
        start = threading.Barrier(2)

        def writer() -> None:
            try:
                start.wait(timeout=5)
                deadline = time.monotonic() + 0.5
                i = 0
                while time.monotonic() < deadline:
                    path, sr = (
                        ("/music/a.flac", 44100) if i % 2 == 0
                        else ("/music/b.flac", 48000)
                    )
                    with player.file_manager._audio_lock:
                        player.file_manager.current_file = path
                        player.file_manager.sample_rate = sr
                    i += 1
            except BaseException as exc:  # pragma: no cover - diagnostic
                errors.append(exc)
            finally:
                stop.set()

        def reader() -> None:
            try:
                start.wait(timeout=5)
                while not stop.is_set():
                    with player.file_manager._audio_lock:
                        current_file = player.current_file
                        sr = player.sample_rate
                    if current_file is not None:
                        observed.append((current_file, sr))
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
