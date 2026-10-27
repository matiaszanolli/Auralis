"""
QueueController - Manages playlist queue and track navigation

Responsibilities:
- Queue management (add, remove, navigate)
- Track sequencing (next, previous)
- Shuffle and repeat modes
- Playlist loading
"""

from collections.abc import Callable
from typing import Any

from ..utils.logging import error, info
from .components import QueueManager
from .queue_loading import QueueLoadingMixin
from .queue_locked_state import QueueLockedStateMixin


class QueueController(QueueLockedStateMixin, QueueLoadingMixin):
    """
    Manages playback queue and track navigation.

    Decoupled from playback state, audio I/O, and prebuffering.
    Only responsible for queue operations and track sequencing.

    """

    def __init__(
        self,
        get_repository_factory: Callable[[], Any],
    ) -> None:
        """
        Initialize queue controller.

        Args:
            get_repository_factory: Callable that returns RepositoryFactory instance (REQUIRED)
        """
        self.queue: QueueManager = QueueManager()
        self.get_repository_factory = get_repository_factory
        self._on_change: Callable[[], None] | None = None

    def set_change_listener(self, listener: Callable[[], None] | None) -> None:
        """Register a callback run after every change to the queue's contents,
        order or wrap-around (#5508).

        AudioPlayer registers ``gapless.invalidate_prebuffer``: the backend
        edits the queue through this controller, never through AudioPlayer's
        own wrappers, so a stale prebuffered "next" track survived every
        reorder/remove/insert. The listener runs after QueueManager._lock is
        released — the gapless engine takes its update_lock before the queue
        lock, so calling it under the queue lock would invert that order.
        """
        self._on_change = listener

    def _notify_changed(self) -> None:
        listener = self._on_change
        if listener is None:
            return
        try:
            listener()
        except Exception as e:
            error(f"Queue change listener failed: {e}")

    def next_track(self) -> dict[str, Any] | None:
        """
        Get next track from queue.

        Returns:
            Track info dict or None if queue empty
        """
        next_track = self.queue.next_track()
        if next_track:
            info(f"Advancing to next track: {next_track.get('title', 'Unknown')}")
        else:
            info("No next track in queue")
        return next_track

    def advance_if_next_matches(self, expected: dict[str, Any]) -> dict[str, Any] | None:
        """
        #3352 (PTS-9): atomic peek+advance for gapless prebuffer commit.

        Used by `GaplessPlaybackEngine.advance_with_prebuffer` to close the
        TOCTOU window between the peek that chose what to load and the
        next_track() that committed the queue advance. Returns the advanced
        track on success, None if the queue mutated between peek and commit
        so the slot no longer holds the expected track.
        """
        advanced = self.queue.advance_if_next_matches(expected)
        if advanced:
            info(f"Advancing to next track: {advanced.get('title', 'Unknown')}")
        return advanced

    def previous_track(self) -> dict[str, Any] | None:
        """
        Get previous track from queue.

        Returns:
            Track info dict or None if at start
        """
        prev_track = self.queue.previous_track()
        if prev_track:
            info(f"Moved to previous track: {prev_track.get('title', 'Unknown')}")
        else:
            info("No previous track in queue")
        return prev_track

    def rollback_index(self, saved_index: int, expected_current: int | None = None) -> bool:
        """#3668: locked rollback of the queue's current_index for use by
        previous_track() when a file load fails. #5582: compare-and-set —
        pass step_previous()'s ``moved_to`` as *expected_current*; the restore
        only applies if nothing moved the index since."""
        return self.queue.rollback_index(saved_index, expected_current)

    def step_previous(self) -> tuple[dict[str, Any] | None, int, int]:
        """#5705: move to the previous track and return ``(track, saved_index,
        moved_to)`` atomically -- the rollback baseline for previous_track(),
        correct even when the move wrapped (#3726's snapshot could not be)."""
        return self.queue.step_previous()

    def get_current_track(self) -> dict[str, Any] | None:
        """Get current track from queue"""
        return self.queue.get_current_track()

    def peek_next_track(self) -> dict[str, Any] | None:
        """
        Peek at next track without advancing queue.

        Useful for prebuffering the next track.
        """
        return self.queue.peek_next()

    def add_track(self, track_info: dict[str, Any]) -> None:
        """Add a track to the queue"""
        self.queue.add_track(track_info)
        self._notify_changed()
        info(f"Added to queue: {track_info.get('title', 'Unknown')}")

    def insert_track(self, index: int, track_info: dict[str, Any]) -> int:
        """Insert a track and return its normalized queue position."""
        position: int = self.queue.insert_track(index, track_info)
        self._notify_changed()
        info(f"Inserted into queue at {position}: {track_info.get('title', 'Unknown')}")
        return position

    def clear_queue(self) -> None:
        """Clear all tracks from queue"""
        self.queue.clear()
        self._notify_changed()
        info("Queue cleared")

    def get_queue_info(self) -> dict[str, Any]:
        """Get detailed queue information as an atomic snapshot (fixes #2470)."""
        return self.queue.get_queue_info()

    def set_shuffle(self, enabled: bool) -> None:
        """Enable/disable shuffle mode.

        Unlike repeat_enabled (consulted live by next_track()/peek_next()),
        shuffle order is baked into the queue's track list at shuffle()-call
        time and never re-derived from the flag — so actually reorder the
        queue here too, matching what the REST endpoint
        (POST /api/player/queue/shuffle -> QueueService.shuffle_queue()/
        unshuffle_queue()) already does by calling QueueManager.shuffle()/
        unshuffle() directly. A flag-only write left set_shuffle() reporting
        shuffle_enabled: True while the queue order stayed untouched (#4986).
        """
        # Route through the locked property setter (#4096) — writing
        # self.queue.shuffle_enabled directly bypassed QueueManager._lock that
        # the shuffle_enabled reader holds.
        #
        # #5315: read the prior state BEFORE overwriting the flag, and skip
        # queue.shuffle() entirely when shuffle was already enabled. Beyond
        # QueueManager.shuffle()'s own snapshot guard (which stops the
        # original order from being lost), a repeated set_shuffle(True) —
        # double click, retried request, UI race — must not even re-shuffle
        # the already-shuffled queue a second time.
        already_enabled = self.shuffle_enabled
        self.shuffle_enabled = enabled
        if enabled:
            if not already_enabled:
                self.queue.shuffle()
        else:
            self.queue.unshuffle()
        self._notify_changed()
        info(f"Shuffle {'enabled' if enabled else 'disabled'}")

    def set_repeat(self, enabled: bool) -> None:
        """Enable/disable repeat mode"""
        # Route through the locked property setter (#4096), as with set_shuffle.
        self.repeat_enabled = enabled
        # Repeat decides whether "next" wraps to the start.
        self._notify_changed()
        info(f"Repeat {'enabled' if enabled else 'disabled'}")

    def has_next_track(self) -> bool:
        """#3692: True iff a subsequent peek_next_track() would return a
        track. Used to gate the auto-advance thread spawn — an
        "is the queue empty" test returns False at end-of-queue if the
        current (last) track is still in the queue, so it can't tell us
        whether there's anything to advance TO."""
        return self.queue.peek_next() is not None

    def get_track_count(self) -> int:
        """Get number of tracks in queue"""
        return self.queue.get_queue_size()

    def get_queue_size(self) -> int:
        """Get queue size (alias for get_track_count)"""
        return self.queue.get_queue_size()

    def remove_track(self, index: int) -> bool:
        """Remove track at specified index"""
        removed: bool = self.queue.remove_track(index)
        if removed:
            self._notify_changed()
        return removed

    def remove_if_index_matches_current(self, index: int) -> tuple[bool, bool]:
        """Atomically remove a track and report whether it was current (#5360).

        See QueueManager.remove_if_index_matches_current for the race this
        closes — a two-step "read current_index, then remove" is vulnerable
        to a concurrent advance/next/previous landing in between.
        """
        result: tuple[bool, bool] = self.queue.remove_if_index_matches_current(index)
        if result[0]:
            self._notify_changed()
        return result

    def get_queue(self) -> list[dict[str, Any]]:
        """Get full queue as list"""
        return self.queue.get_queue()

    def shuffle(self) -> None:
        """Shuffle the queue, keeping the current track in place."""
        self.queue.shuffle()
        # #5587: keep the flag consistent with the order. Only set_shuffle
        # wrote it, so a REST shuffle (QueueService.shuffle_queue → this
        # method) left get_queue_info()['shuffle_enabled'] False while the
        # queue was actually shuffled — and an unshuffle() after
        # set_shuffle(True) left it True over the restored order. The locked
        # property setter is the same route set_shuffle uses (#4096).
        self.shuffle_enabled = True
        self._notify_changed()

    def unshuffle(self) -> bool:
        """Restore the pre-shuffle queue order. Returns True if restored."""
        restored: bool = self.queue.unshuffle()
        if restored:
            self.shuffle_enabled = False
            self._notify_changed()
        return restored

    def reorder_tracks(self, new_order: list[int]) -> bool:
        """Reorder tracks according to new index order"""
        reordered: bool = self.queue.reorder_tracks(new_order)
        if reordered:
            self._notify_changed()
        return reordered

    def move_track(self, from_index: int, to_index: int) -> bool:
        """Move one track while preserving the currently selected track."""
        moved: bool = self.queue.move_track(from_index, to_index)
        if moved:
            self._notify_changed()
        return moved

