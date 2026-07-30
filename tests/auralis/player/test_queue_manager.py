"""
Tests for QueueManager.shuffle()/unshuffle() snapshot invalidation (#4525)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

unshuffle() restores self.tracks from a snapshot taken by shuffle(). Any
queue mutation performed while shuffled must invalidate that snapshot so
unshuffle() declines to restore (returns False) instead of silently
discarding the mutation.
"""

import pytest

from auralis.player.components.queue_manager import QueueManager


def _track(n: int) -> dict:
    return {'id': n, 'title': f'Track {n}', 'file_path': f'/music/track_{n}.mp3'}


def _queue(n: int) -> QueueManager:
    q = QueueManager()
    q.add_tracks([_track(i) for i in range(n)])
    return q


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda q: q.add_track(_track(99)), id="add_track"),
        pytest.param(lambda q: q.add_tracks([_track(98), _track(99)]), id="add_tracks"),
        pytest.param(lambda q: q.remove_track(0), id="remove_track"),
        pytest.param(lambda q: q.remove_tracks([0, 1]), id="remove_tracks"),
        pytest.param(lambda q: q.reorder_tracks(list(reversed(range(4)))), id="reorder_tracks"),
        pytest.param(lambda q: q.clear(), id="clear"),
    ],
)
def test_mutation_while_shuffled_invalidates_snapshot(mutate):
    q = _queue(4)
    q.shuffle()
    mutate(q)

    assert q.unshuffle() is False
    assert q._pre_shuffle_tracks is None
    assert q._pre_shuffle_index == -1


def test_add_track_while_shuffled_survives_unshuffle_decline():
    q = _queue(2)
    q.shuffle()
    q.add_track(_track(99))

    assert q.unshuffle() is False
    ids = {t['id'] for t in q.get_queue()}
    assert 99 in ids


def test_remove_track_while_shuffled_does_not_resurrect():
    q = _queue(3)
    q.shuffle()
    # Remove whichever track ended up at index 0 post-shuffle.
    removed_id = q.get_queue()[0]['id']
    q.remove_track(0)

    assert q.unshuffle() is False
    ids = {t['id'] for t in q.get_queue()}
    assert removed_id not in ids


def test_clean_shuffle_unshuffle_round_trip_restores_order():
    q = _queue(5)
    original_order = [t['id'] for t in q.get_queue()]
    original_index = q.current_index

    q.shuffle()
    assert q.unshuffle() is True

    assert [t['id'] for t in q.get_queue()] == original_order
    assert q.current_index == original_index


def test_unshuffle_without_prior_shuffle_returns_false():
    q = _queue(3)
    assert q.unshuffle() is False
