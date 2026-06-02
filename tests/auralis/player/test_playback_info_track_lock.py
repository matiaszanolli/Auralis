"""
Regression test: get_playback_info reads current_track under _position_lock (#4102)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

get_playback_info() snapshotted position/state/current_file inside _position_lock
but read self.current_track AFTER the block exited. The write side is locked
under _position_lock (#3786), so a transition between the lock release and the
current_track read could pair the new track's position with the old track's
metadata for one WebSocket poll. The current_track snapshot is now taken inside
the same lock acquisition.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import threading


class _LockProbe:
    """Wraps the real lock and tracks current acquisition depth."""

    def __init__(self, real):
        self._real = real
        self.depth = 0

    def __enter__(self):
        self._real.acquire()
        self.depth += 1
        return self

    def __exit__(self, *exc):
        self.depth -= 1
        self._real.release()
        return False


class _ProbeTrack:
    """Track stand-in that records whether to_dict() ran under the lock."""

    def __init__(self, probe: _LockProbe, ident: int):
        self._probe = probe
        self.ident = ident
        self.read_while_locked: bool | None = None

    def to_dict(self) -> dict:
        self.read_while_locked = self._probe.depth > 0
        return {"id": self.ident}


def test_current_track_read_under_position_lock(integration_manager):
    """current_track.to_dict() must execute while _position_lock is held (#4102)."""
    mgr = integration_manager
    probe = _LockProbe(mgr._position_lock)
    mgr._position_lock = probe
    track = _ProbeTrack(probe, 42)
    mgr.current_track = track  # type: ignore[assignment]

    info = mgr.get_playback_info()

    assert track.read_while_locked is True, (
        "current_track must be snapshotted inside the _position_lock block"
    )
    assert info["library"]["current_track"] == {"id": 42}
    # Sanity: the probe was balanced (every acquire released).
    assert probe.depth == 0


def test_playback_info_handles_no_current_track(integration_manager):
    """None current_track still produces a valid snapshot."""
    mgr = integration_manager
    mgr.current_track = None
    info = mgr.get_playback_info()
    assert info["library"]["current_track"] is None
    assert "playback" in info


def test_concurrent_swap_never_splits_track_and_position(integration_manager):
    """Polling get_playback_info while current_track is swapped under the lock
    must never observe a half-written track (e.g. None title with a set id)."""
    mgr = integration_manager
    stop = threading.Event()
    errors: list[str] = []

    class _Track:
        def __init__(self, ident):
            self.ident = ident

        def to_dict(self):
            # Two-field read that must be observed atomically as one track.
            return {"id": self.ident, "title": f"track-{self.ident}"}

    def writer():
        i = 0
        while not stop.is_set():
            i += 1
            with mgr._position_lock:
                mgr.current_track = _Track(i)  # type: ignore[assignment]

    def reader():
        while not stop.is_set():
            ct = mgr.get_playback_info()["library"]["current_track"]
            if ct is not None and ct["title"] != f"track-{ct['id']}":
                errors.append(f"split snapshot: {ct}")
                return

    w = threading.Thread(target=writer)
    readers = [threading.Thread(target=reader) for _ in range(6)]
    w.start()
    for r in readers:
        r.start()
    threading.Event().wait(0.5)
    stop.set()
    w.join()
    for r in readers:
        r.join()

    assert not errors, errors[:3]
