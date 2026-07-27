"""
Regression test: get_playback_info pairs current_track with position (#4102, #4552)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

get_playback_info() snapshotted position/state/current_file inside _position_lock
but read self.current_track AFTER the block exited. The write side is locked
under _position_lock (#3786), so a transition between the lock release and the
current_track read could pair the new track's position with the old track's
metadata for one WebSocket poll (#4102).

#4552 kept that invariant but changed *how* it is achieved. #4102's fix called
`current_track.to_dict()` inside the lock; because `to_dict()` walks lazily
loaded `artists`/`album` relationships, that put a library SQL round-trip — and
a possible DetachedInstanceError — inside a player lock, inverting the
documented Player-lock -> Library-session ordering. The dict is now
materialised at *assignment* time in `set_current_track`, outside the lock, and
swapped atomically with the ORM reference under it.

So the assertion here inverts: `to_dict()` must NOT run while _position_lock is
held, while the returned `library.current_track` must still describe the same
track as `playback.position_seconds`.

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


def test_to_dict_never_runs_under_position_lock(integration_manager):
    """to_dict() must NOT execute while _position_lock is held (#4552).

    It walks lazily loaded relationships, so calling it under the lock puts a
    library SQL round-trip inside a player lock.
    """
    mgr = integration_manager
    probe = _LockProbe(mgr._position_lock)
    mgr._position_lock = probe
    track = _ProbeTrack(probe, 42)

    mgr.current_track = track  # type: ignore[assignment]
    assert track.read_while_locked is False, (
        "to_dict() ran while _position_lock was held — #4552 requires the "
        "snapshot to be materialised before the lock is taken"
    )

    # Reading must not touch the ORM object again at all.
    track.read_while_locked = None
    info = mgr.get_playback_info()

    assert track.read_while_locked is None, (
        "get_playback_info must serve the pre-materialised dict, not re-call "
        "to_dict() on the ORM object"
    )
    assert info["library"]["current_track"] == {"id": 42}
    # Sanity: the probe was balanced (every acquire released).
    assert probe.depth == 0


def test_state_change_callback_serves_materialised_dict(integration_manager):
    """The playback state-change callback must not touch the ORM either."""
    mgr = integration_manager
    probe = _LockProbe(mgr._position_lock)
    mgr._position_lock = probe
    track = _ProbeTrack(probe, 7)
    mgr.current_track = track  # type: ignore[assignment]

    received: list[dict] = []
    mgr.add_callback(received.append)

    track.read_while_locked = None
    mgr._on_playback_state_change({})

    assert track.read_while_locked is None, (
        "_on_playback_state_change must not call to_dict() (#4552)"
    )
    assert received and received[0]["current_track"] == {"id": 7}
    assert probe.depth == 0


def test_detached_track_does_not_raise(integration_manager):
    """A track whose session has closed degrades to None, and never raises
    from inside a lock or out of the playback callback (#4552)."""
    from sqlalchemy.orm.exc import DetachedInstanceError

    mgr = integration_manager

    class _DetachedTrack:
        def to_dict(self):
            raise DetachedInstanceError("session closed")

    mgr.current_track = _DetachedTrack()  # type: ignore[assignment]

    info = mgr.get_playback_info()
    assert info["library"]["current_track"] is None

    mgr._on_playback_state_change({})  # must not raise


def test_raw_attribute_write_keeps_snapshot_in_sync(integration_manager):
    """`current_track` is a property, so even a direct assignment refreshes the
    materialised dict — no stale snapshot can be served (#4552 WIRING)."""
    mgr = integration_manager

    class _T:
        def __init__(self, i):
            self.i = i

        def to_dict(self):
            return {"id": self.i}

    mgr.current_track = _T(1)  # type: ignore[assignment]
    assert mgr.get_playback_info()["library"]["current_track"] == {"id": 1}

    mgr.current_track = _T(2)  # type: ignore[assignment]
    assert mgr.get_playback_info()["library"]["current_track"] == {"id": 2}

    mgr.current_track = None
    assert mgr.get_playback_info()["library"]["current_track"] is None


def test_playback_info_handles_no_current_track(integration_manager):
    """None current_track still produces a valid snapshot."""
    mgr = integration_manager
    mgr.current_track = None
    info = mgr.get_playback_info()
    assert info["library"]["current_track"] is None
    assert "playback" in info


def test_session_stats_read_under_stats_lock(integration_manager):
    """tracks_played must never be observed torn or moving backwards (#4552).

    record_track_completion holds _stats_lock for the write (#2472); the read
    side used to be unguarded.
    """
    mgr = integration_manager
    stop = threading.Event()
    errors: list[str] = []
    observations: list[int] = []

    def writer():
        while not stop.is_set():
            mgr.record_track_completion()

    def reader():
        last = 0
        while not stop.is_set():
            played = mgr.get_playback_info()["session"]["tracks_played"]
            if played < last:
                errors.append(f"tracks_played went backwards: {last} -> {played}")
                return
            last = played
            observations.append(played)

    w = threading.Thread(target=writer)
    readers = [threading.Thread(target=reader) for _ in range(4)]
    w.start()
    for r in readers:
        r.start()
    threading.Event().wait(0.3)
    stop.set()
    w.join()
    for r in readers:
        r.join()

    assert not errors, errors[:3]
    assert observations
    # Never exceeds what the writer actually issued.
    assert max(observations) <= mgr.tracks_played


def test_get_playback_info_takes_stats_lock(integration_manager):
    """White-box guard so the read side cannot silently drop the lock again."""
    import inspect

    source = inspect.getsource(type(integration_manager).get_playback_info)
    assert "_stats_lock" in source, (
        "get_playback_info must read session counters under _stats_lock (#4552)"
    )


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
