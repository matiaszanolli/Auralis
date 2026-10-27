"""Regression tests: rollback_index() is a compare-and-set (#5582)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

previous_track() moves the queue index, then does a blocking load_file()
with no queue lock held. An unconditional rollback wrote the saved integer
back even when a queue edit had moved the index during the load — the
probe landed `current_index == len(tracks)`: no current track,
`peek_next` None, and a phantom previous track. The rollback is now a
compare-and-set against the index previous_track() moved to, plus a clamp
to the live queue bounds.

Real QueueManager throughout — the bug is in its locking and index
arithmetic, which a mock would simply re-enact.
"""

from auralis.player.components.queue_manager import QueueManager


def _track(n: int) -> dict:
    return {'id': n, 'title': f'Track {n}', 'filepath': f'/music/track_{n}.mp3'}


def _queue_ab_starting_at_b() -> QueueManager:
    """[A, B] with the pointer on B (index 1) — the issue probe's setup."""
    qm = QueueManager()
    qm.add_track(_track(1))
    qm.add_track(_track(2))
    qm.current_index = 1
    return qm


class TestRollbackIndexCompareAndSet:
    def test_untouched_queue_restores_the_saved_index(self):
        qm = _queue_ab_starting_at_b()
        saved = qm.snapshot_index()  # 1

        qm.previous_track()  # moves to 0

        assert qm.rollback_index(saved, expected_current=saved - 1) is True
        assert qm.current_index == saved

    def test_edit_during_the_load_is_not_clobbered(self):
        """The probe: a remove_track lands between the move and the rollback.
        The restore must stay within the live queue bounds instead of writing
        the stale integer back over the edit."""
        qm = _queue_ab_starting_at_b()
        saved = qm.snapshot_index()  # 1

        qm.previous_track()  # moves to 0
        qm.remove_track(0)  # queue is now [B]

        qm.rollback_index(saved, expected_current=saved - 1)

        assert -1 <= qm.current_index <= len(qm.tracks) - 1
        assert qm.get_current_track() is not None

    def test_mismatched_expected_current_skips_the_write(self):
        """An edit that moved the index somewhere else wins: no stale write."""
        qm = _queue_ab_starting_at_b()
        qm.previous_track()  # → 0

        # The edit moved the pointer to 1; the rollback expected 0.
        qm.current_index = 1

        assert qm.rollback_index(0, expected_current=0) is False
        assert qm.current_index == 1

    def test_no_expected_current_keeps_the_legacy_unconditional_form(self):
        """Callers without a move-to index (none today) keep the old
        behaviour, still clamped to the live queue bounds."""
        qm = _queue_ab_starting_at_b()
        qm.previous_track()  # → 0

        assert qm.rollback_index(1) is True
        assert qm.current_index == 1

    def test_clamped_to_bounds_when_the_queue_shrunk(self):
        """CAS matches (index untouched) but the queue lost a track: the
        restored value clamps to the last live slot instead of len(tracks)."""
        qm = _queue_ab_starting_at_b()
        qm.previous_track()  # → 0

        # Shrink by replacing the queue contents without touching the index.
        qm.tracks.pop()

        assert qm.rollback_index(1, expected_current=0) is True
        assert qm.current_index == 0


class TestWrappedPreviousMove:
    """#5705: with repeat on, previous from the first track lands on the LAST
    one, so the compare-and-set baseline is the reported ``moved_to`` index --
    ``saved_index - 1`` (-1) never matched and the rollback was skipped."""

    def _three_tracks(self, current_index: int) -> QueueManager:
        qm = QueueManager()
        for n in (1, 2, 3):
            qm.add_track(_track(n))
        qm.repeat_enabled = True
        qm.current_index = current_index
        return qm

    def test_step_previous_reports_the_wrapped_destination(self):
        qm = self._three_tracks(0)

        track, saved, moved_to = qm.step_previous()

        assert (saved, moved_to) == (0, 2)
        assert track == qm.tracks[2]

    def test_failed_load_after_a_wrap_restores_the_first_track(self):
        qm = self._three_tracks(0)
        _, saved, moved_to = qm.step_previous()

        assert qm.rollback_index(saved, expected_current=moved_to) is True

        assert qm.current_index == 0
        assert qm.get_current_track() == qm.tracks[0]

    def test_failed_load_after_a_wrap_from_index_minus_one_restores_it(self):
        qm = self._three_tracks(-1)
        _, saved, moved_to = qm.step_previous()

        assert (saved, moved_to) == (-1, 2)
        assert qm.rollback_index(saved, expected_current=moved_to) is True
        assert qm.current_index == -1

    def test_non_wrapping_move_reports_saved_minus_one(self):
        qm = self._three_tracks(2)

        _, saved, moved_to = qm.step_previous()

        assert (saved, moved_to) == (2, 1)

    def test_nothing_moves_at_the_start_without_repeat(self):
        qm = self._three_tracks(0)
        qm.repeat_enabled = False

        assert qm.step_previous() == (None, 0, 0)
        assert qm.current_index == 0

    def test_an_edit_during_the_load_still_wins_after_a_wrap(self):
        qm = self._three_tracks(0)
        _, saved, moved_to = qm.step_previous()
        qm.remove_track(0)  # queue is now [2, 3]; the pointer follows

        assert qm.rollback_index(saved, expected_current=moved_to) is False
        assert -1 <= qm.current_index <= len(qm.tracks) - 1

    def test_empty_queue_reports_no_move(self):
        assert QueueManager().step_previous() == (None, -1, -1)
