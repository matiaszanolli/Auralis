"""
Regression test for #3434 — end-of-track auto-advance must be atomic.

Pre-fix: the end-of-track check was guarded by `_audio_lock`, but the
test-and-spawn block (`if not _auto_advancing.is_set(): _auto_advancing.set();
spawn thread`) was OUTSIDE the lock. `Event.is_set()` followed by `.set()`
is a classic TOCTOU race — two concurrent `get_audio_chunk` callers could
both see the flag unset and both spawn an advance thread, double-skipping
the next track.

Post-fix: the test-and-spawn is moved inside the same `_audio_lock` block.
Spawning a thread doesn't block on the lock; the spawned thread acquires
the lock independently when it runs.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def short_audio_files():
    """Create two tiny test WAVs (0.1s each) so end-of-track triggers fast."""
    audio_dir = tempfile.mkdtemp(prefix="player_eot_test_")
    sample_rate = 44100
    duration = 0.1   # 4410 samples — small enough that end_of_track fires quickly
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples)

    paths: dict[str, str] = {}
    for i, freq in enumerate([440.0, 523.25]):
        path = os.path.join(audio_dir, f"track{i + 1}.wav")
        sf.write(path, 0.3 * np.sin(2 * np.pi * freq * t), sample_rate)
        paths[f"track{i + 1}"] = path

    yield paths
    shutil.rmtree(audio_dir, ignore_errors=True)


def test_concurrent_end_of_track_only_spawns_one_advance(
    enhanced_player, short_audio_files,
):
    """Fire many concurrent get_audio_chunk calls at end-of-track; assert
    exactly ONE auto-advance thread is spawned (not one per caller).

    Forces the TOCTOU race window open by injecting a small sleep between
    `Event.is_set()` and `Event.set()` via a monkeypatched `is_set`. On the
    pre-fix code (test-and-set OUTSIDE the lock), this reliably reproduces
    the double-spawn. On the post-fix code (test-and-set INSIDE the lock),
    the lock serializes the callers and only one spawn happens regardless
    of the injected delay.
    """
    import time

    player = enhanced_player

    # Load track 1 and queue track 2 so auto-advance has somewhere to go.
    assert player.load_file(short_audio_files["track1"])
    player.queue.add_track({
        "title": "Track 2",
        "filepath": short_audio_files["track2"],
        "id": 2,
        "duration": 0.1,
    })
    assert not player.queue.is_queue_empty()

    # Force the player into a state where end_of_track will fire on the next
    # get_audio_chunk: mark playing and seek to near end.
    player.playback.play()
    total_samples = player.file_manager.get_total_samples()
    player.playback.seek(max(0, total_samples - 16), total_samples)

    # Spy that records invocations without clearing the flag.
    invocations: list[int] = []
    original_advance = player._auto_advance_next

    def spy_advance(generation: int) -> None:
        invocations.append(generation)

    player._auto_advance_next = spy_advance

    # Widen the TOCTOU window: when is_set() returns False, sleep briefly
    # to give other threads a chance to also see False before we .set().
    # On pre-fix code (lock released before this sequence) this makes the
    # race deterministic. On post-fix code the lock prevents reentry.
    original_is_set = player._auto_advancing.is_set

    def slow_is_set() -> bool:
        result = original_is_set()
        if not result:
            time.sleep(0.005)   # 5ms — wide enough to lose any race
        return result

    player._auto_advancing.is_set = slow_is_set     # type: ignore[method-assign]

    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(player.get_audio_chunk, 1024) for _ in range(8)]
            for f in futures:
                f.result()
    finally:
        player._auto_advance_next = original_advance
        player._auto_advancing.is_set = original_is_set    # type: ignore[method-assign]

    # Contract: exactly ONE advance spawned per end-of-track event.
    assert len(invocations) == 1, (
        f"Expected exactly 1 auto-advance spawn for one end-of-track event, "
        f"got {len(invocations)} (generations: {invocations}) — #3434 regressed"
    )


def test_single_get_audio_chunk_at_end_spawns_one_advance(
    enhanced_player, short_audio_files,
):
    """Sanity check: a SINGLE call at end-of-track still spawns one advance.
    Guards against the fix accidentally suppressing all spawns."""
    player = enhanced_player

    assert player.load_file(short_audio_files["track1"])
    player.queue.add_track({
        "title": "Track 2",
        "filepath": short_audio_files["track2"],
        "id": 2,
        "duration": 0.1,
    })
    player.playback.play()
    total_samples = player.file_manager.get_total_samples()
    player.playback.seek(max(0, total_samples - 16), total_samples)

    invocations: list[int] = []
    original = player._auto_advance_next

    def spy(generation: int) -> None:
        invocations.append(generation)

    player._auto_advance_next = spy
    try:
        player.get_audio_chunk(1024)
    finally:
        player._auto_advance_next = original

    assert len(invocations) == 1, (
        f"Single end-of-track call must spawn exactly 1 advance, got {len(invocations)}"
    )
