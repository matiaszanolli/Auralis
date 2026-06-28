"""
AudioPlayer.position setter holds _audio_lock across read + seek (#4141).

The setter read max_samples (get_total_samples) and called playback.seek in two
separate lock acquisitions; a gapless transition in between could make
max_samples stale. It now mirrors AudioPlayer.seek() and holds _audio_lock across
both, so the read and the seek are atomic.
"""

from auralis.player.enhanced_audio_player import AudioPlayer


def test_position_setter_holds_lock_across_read_and_seek(get_repository_factory_callable):
    player = AudioPlayer(get_repository_factory=get_repository_factory_callable)

    events: list[str] = []
    real_lock = player.file_manager._audio_lock

    class SpyLock:
        def __enter__(self):
            events.append("enter")
            return real_lock.__enter__()

        def __exit__(self, *exc):
            events.append("exit")
            return real_lock.__exit__(*exc)

        def acquire(self, *a, **k):
            return real_lock.acquire(*a, **k)

        def release(self):
            return real_lock.release()

    player.file_manager._audio_lock = SpyLock()
    player.file_manager.get_total_samples = lambda: (events.append("gts"), 1000)[1]
    player.playback.seek = lambda value, max_samples: events.append(f"seek:{max_samples}")

    player.position = 42

    # Both the read and the seek happen inside a single lock scope.
    assert events == ["enter", "gts", "seek:1000", "exit"]
