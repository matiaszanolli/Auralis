"""
QueueManager.advance_if_next_matches — #3352 (PTS-9) regression coverage.

Verifies the atomic peek+match+commit operation introduced to close the
TOCTOU window in `GaplessPlaybackEngine.advance_with_prebuffer`. The engine
used to peek the next track, process audio, and only then commit the queue
advance — leaving room for a concurrent mutation to put a different track in
the slot.

Acceptance criteria (#3352):
- Track prebuffered == track committed, even under concurrent queue mutation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.player.components.queue_manager import QueueManager


def _make_track(track_id: int, path: str | None = None) -> dict:
    return {
        "id": track_id,
        "title": f"Track {track_id}",
        "file_path": path or f"/music/track_{track_id}.flac",
    }


class TestAdvanceIfNextMatches:
    def setup_method(self) -> None:
        self.qm = QueueManager()
        self.qm.add_tracks([_make_track(i) for i in range(5)])
        self.qm.set_track_by_index(0)

    def test_advances_when_next_slot_matches(self) -> None:
        expected = self.qm.peek_next()
        assert expected is not None
        assert expected["id"] == 1

        advanced = self.qm.advance_if_next_matches(expected)

        assert advanced is not None
        assert advanced["id"] == 1
        assert self.qm.current_index == 1

    def test_returns_none_and_does_not_advance_on_id_mismatch(self) -> None:
        expected = self.qm.peek_next()
        assert expected is not None
        # Simulate a concurrent reorder/replace that put a different track
        # into the slot we peeked at.
        self.qm.tracks[1] = _make_track(99)

        advanced = self.qm.advance_if_next_matches(expected)

        assert advanced is None
        assert self.qm.current_index == 0  # untouched

    def test_returns_none_when_queue_shrunk_below_next_slot(self) -> None:
        expected = self.qm.peek_next()
        assert expected is not None
        # Concurrent removal of everything after the current track.
        self.qm.tracks = self.qm.tracks[:1]

        advanced = self.qm.advance_if_next_matches(expected)

        assert advanced is None
        assert self.qm.current_index == 0

    def test_returns_none_when_queue_cleared(self) -> None:
        expected = self.qm.peek_next()
        assert expected is not None
        self.qm.clear()

        advanced = self.qm.advance_if_next_matches(expected)

        assert advanced is None
        # clear() set current_index back to -1, not the original 0.
        assert self.qm.current_index == -1

    def test_falls_back_to_path_when_id_missing(self) -> None:
        # Tracks without explicit ids (e.g. directly-loaded files) match by path.
        qm = QueueManager()
        qm.add_tracks([
            {"title": "a", "file_path": "/a.flac"},
            {"title": "b", "file_path": "/b.flac"},
        ])
        qm.set_track_by_index(0)
        expected = qm.peek_next()
        assert expected is not None

        advanced = qm.advance_if_next_matches(expected)

        assert advanced is not None
        assert advanced["file_path"] == "/b.flac"
        assert qm.current_index == 1

    def test_repeat_mode_wraps_when_matching(self) -> None:
        # At the end of the queue with repeat enabled, peek_next() returns
        # tracks[0]; advance_if_next_matches() must wrap to 0 as well.
        self.qm.set_track_by_index(4)
        self.qm.repeat_enabled = True
        expected = self.qm.peek_next()
        assert expected is not None
        assert expected["id"] == 0

        advanced = self.qm.advance_if_next_matches(expected)

        assert advanced is not None
        assert advanced["id"] == 0
        assert self.qm.current_index == 0

    def test_no_advance_at_end_without_repeat(self) -> None:
        self.qm.set_track_by_index(4)
        # Caller peeks first — peek_next() correctly returns None.
        expected = self.qm.peek_next()
        assert expected is None

        # If the caller somehow constructs an expected track and calls anyway,
        # the method must refuse to advance past the end.
        synthetic = _make_track(0)
        advanced = self.qm.advance_if_next_matches(synthetic)

        assert advanced is None
        assert self.qm.current_index == 4
