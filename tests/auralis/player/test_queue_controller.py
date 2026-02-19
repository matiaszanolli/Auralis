"""
Tests for QueueController (#2290)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Covers all public methods:
- next_track / previous_track navigation
- Repeat mode (none / enabled — wraps at boundaries)
- Shuffle flag pass-through
- reorder_tracks (valid / invalid orders, current-index tracking)
- remove_track (index adjustment)
- set_queue / add_track / add_tracks / clear
- get_queue_info / get_track_count / is_queue_empty
- peek_next_track
- Library-backed methods: add_track_from_library, search_and_add, load_playlist
"""

from unittest.mock import MagicMock

import pytest

from auralis.player.queue_controller import QueueController


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _track(n: int) -> dict:
    return {'id': n, 'title': f'Track {n}', 'filepath': f'/music/track_{n}.mp3'}


def _make_controller() -> tuple[QueueController, MagicMock]:
    """Return (controller, mock_factory) for library-backed tests."""
    mock_factory = MagicMock()
    ctrl = QueueController(get_repository_factory=lambda: mock_factory)
    return ctrl, mock_factory


def _loaded_controller(n: int = 3) -> QueueController:
    """Return controller with n tracks pre-loaded, current_index=0."""
    ctrl, _ = _make_controller()
    for i in range(1, n + 1):
        ctrl.add_track(_track(i))
    ctrl.current_index = 0
    return ctrl


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_queue_starts_empty(self):
        ctrl, _ = _make_controller()
        assert ctrl.is_queue_empty()

    def test_current_index_starts_at_minus_one(self):
        ctrl, _ = _make_controller()
        assert ctrl.current_index == -1

    def test_shuffle_starts_disabled(self):
        ctrl, _ = _make_controller()
        assert ctrl.shuffle_enabled is False

    def test_repeat_starts_disabled(self):
        ctrl, _ = _make_controller()
        assert ctrl.repeat_enabled is False


# ---------------------------------------------------------------------------
# add_track / add_tracks / set_queue
# ---------------------------------------------------------------------------

class TestAddTrack:
    def test_add_single_track_increases_count(self):
        ctrl, _ = _make_controller()
        ctrl.add_track(_track(1))
        assert ctrl.get_track_count() == 1

    def test_add_tracks_bulk(self):
        ctrl, _ = _make_controller()
        ctrl.add_tracks([_track(1), _track(2), _track(3)])
        assert ctrl.get_track_count() == 3

    def test_add_track_preserves_payload(self):
        ctrl, _ = _make_controller()
        ctrl.add_track({'id': 99, 'title': 'Test', 'filepath': '/x.mp3'})
        q = ctrl.get_queue()
        assert q[0]['id'] == 99
        assert q[0]['title'] == 'Test'

    def test_set_queue_with_dicts(self):
        ctrl, _ = _make_controller()
        tracks = [_track(i) for i in range(1, 4)]
        ctrl.set_queue(tracks)
        assert ctrl.get_track_count() == 3
        assert ctrl.current_index == 0

    def test_set_queue_with_filepaths(self):
        ctrl, _ = _make_controller()
        ctrl.set_queue(['/a.mp3', '/b.mp3'])
        q = ctrl.get_queue()
        assert q[0]['filepath'] == '/a.mp3'
        assert q[1]['filepath'] == '/b.mp3'

    def test_set_queue_respects_start_index(self):
        ctrl, _ = _make_controller()
        ctrl.set_queue([_track(1), _track(2), _track(3)], start_index=2)
        assert ctrl.current_index == 2

    def test_set_queue_clamps_start_index_to_last(self):
        ctrl, _ = _make_controller()
        ctrl.set_queue([_track(1), _track(2)], start_index=99)
        assert ctrl.current_index == 1

    def test_set_queue_replaces_existing(self):
        ctrl, _ = _make_controller()
        ctrl.add_tracks([_track(i) for i in range(10)])
        ctrl.set_queue([_track(1)])
        assert ctrl.get_track_count() == 1


# ---------------------------------------------------------------------------
# Navigation: next_track / previous_track
# ---------------------------------------------------------------------------

class TestNavigation:
    def test_next_track_advances_index(self):
        ctrl = _loaded_controller(3)
        first = ctrl.get_current_track()
        second = ctrl.next_track()
        assert ctrl.current_index == 1
        assert second['id'] != first['id']

    def test_next_track_returns_correct_track(self):
        ctrl = _loaded_controller(3)
        nxt = ctrl.next_track()
        assert nxt['id'] == 2

    def test_next_track_at_end_without_repeat_returns_none(self):
        ctrl = _loaded_controller(2)
        ctrl.next_track()          # → index 1 (last)
        result = ctrl.next_track() # → past the end
        assert result is None

    def test_next_track_does_not_advance_past_end_without_repeat(self):
        ctrl = _loaded_controller(2)
        ctrl.current_index = 1     # already at last
        ctrl.next_track()
        assert ctrl.current_index == 1

    def test_previous_track_decrements_index(self):
        ctrl = _loaded_controller(3)
        ctrl.current_index = 2
        ctrl.previous_track()
        assert ctrl.current_index == 1

    def test_previous_track_returns_correct_track(self):
        ctrl = _loaded_controller(3)
        ctrl.current_index = 2
        prev = ctrl.previous_track()
        assert prev['id'] == 2

    def test_previous_track_at_start_without_repeat_returns_none(self):
        ctrl = _loaded_controller(3)
        ctrl.current_index = 0
        result = ctrl.previous_track()
        assert result is None

    def test_next_on_empty_queue_returns_none(self):
        ctrl, _ = _make_controller()
        assert ctrl.next_track() is None

    def test_previous_on_empty_queue_returns_none(self):
        ctrl, _ = _make_controller()
        assert ctrl.previous_track() is None

    def test_get_current_track_with_valid_index(self):
        ctrl = _loaded_controller(3)
        current = ctrl.get_current_track()
        assert current['id'] == 1

    def test_get_current_track_when_index_minus_one(self):
        ctrl, _ = _make_controller()
        ctrl.add_track(_track(1))
        # current_index stays -1 until navigation
        assert ctrl.get_current_track() is None

    def test_peek_next_does_not_advance_index(self):
        ctrl = _loaded_controller(3)
        before = ctrl.current_index
        ctrl.peek_next_track()
        assert ctrl.current_index == before

    def test_peek_next_returns_correct_track(self):
        ctrl = _loaded_controller(3)
        peeked = ctrl.peek_next_track()
        assert peeked['id'] == 2

    def test_peek_next_at_end_without_repeat_returns_none(self):
        ctrl = _loaded_controller(2)
        ctrl.current_index = 1
        assert ctrl.peek_next_track() is None


# ---------------------------------------------------------------------------
# Repeat mode
# ---------------------------------------------------------------------------

class TestRepeatMode:
    def test_set_repeat_true(self):
        ctrl, _ = _make_controller()
        ctrl.set_repeat(True)
        assert ctrl.repeat_enabled is True

    def test_set_repeat_false(self):
        ctrl, _ = _make_controller()
        ctrl.set_repeat(True)
        ctrl.set_repeat(False)
        assert ctrl.repeat_enabled is False

    def test_next_at_end_with_repeat_wraps_to_first(self):
        ctrl = _loaded_controller(3)
        ctrl.set_repeat(True)
        ctrl.current_index = 2   # last track
        nxt = ctrl.next_track()
        assert ctrl.current_index == 0
        assert nxt['id'] == 1

    def test_previous_at_start_with_repeat_wraps_to_last(self):
        ctrl = _loaded_controller(3)
        ctrl.set_repeat(True)
        ctrl.current_index = 0
        prev = ctrl.previous_track()
        assert ctrl.current_index == 2
        assert prev['id'] == 3

    def test_peek_next_with_repeat_at_end_returns_first(self):
        ctrl = _loaded_controller(3)
        ctrl.set_repeat(True)
        ctrl.current_index = 2
        peeked = ctrl.peek_next_track()
        assert peeked['id'] == 1

    def test_repeat_property_setter(self):
        ctrl, _ = _make_controller()
        ctrl.repeat_enabled = True
        assert ctrl.repeat_enabled is True


# ---------------------------------------------------------------------------
# Shuffle mode
# ---------------------------------------------------------------------------

class TestShuffleMode:
    def test_set_shuffle_true(self):
        ctrl, _ = _make_controller()
        ctrl.set_shuffle(True)
        assert ctrl.shuffle_enabled is True

    def test_set_shuffle_false(self):
        ctrl, _ = _make_controller()
        ctrl.set_shuffle(True)
        ctrl.set_shuffle(False)
        assert ctrl.shuffle_enabled is False

    def test_shuffle_property_setter(self):
        ctrl, _ = _make_controller()
        ctrl.shuffle_enabled = True
        assert ctrl.shuffle_enabled is True

    def test_shuffle_does_not_affect_queue_length(self):
        ctrl = _loaded_controller(5)
        ctrl.set_shuffle(True)
        assert ctrl.get_track_count() == 5


# ---------------------------------------------------------------------------
# reorder_tracks
# ---------------------------------------------------------------------------

class TestReorderTracks:
    def test_reorder_reverses_queue(self):
        ctrl = _loaded_controller(3)  # ids: 1,2,3
        result = ctrl.reorder_tracks([2, 1, 0])
        assert result is True
        ids = [t['id'] for t in ctrl.get_queue()]
        assert ids == [3, 2, 1]

    def test_reorder_preserves_current_track(self):
        ctrl = _loaded_controller(3)
        ctrl.current_index = 1  # Track 2
        ctrl.reorder_tracks([2, 1, 0])  # reverse → Track 2 is now at index 1
        assert ctrl.get_current_track()['id'] == 2

    def test_reorder_wrong_length_returns_false(self):
        ctrl = _loaded_controller(3)
        result = ctrl.reorder_tracks([0, 1])  # too short
        assert result is False

    def test_reorder_duplicate_indices_returns_false(self):
        ctrl = _loaded_controller(3)
        result = ctrl.reorder_tracks([0, 0, 2])  # duplicate 0
        assert result is False

    def test_reorder_identity_returns_true(self):
        ctrl = _loaded_controller(3)
        result = ctrl.reorder_tracks([0, 1, 2])
        assert result is True
        ids = [t['id'] for t in ctrl.get_queue()]
        assert ids == [1, 2, 3]


# ---------------------------------------------------------------------------
# remove_track
# ---------------------------------------------------------------------------

class TestRemoveTrack:
    def test_remove_track_decreases_count(self):
        ctrl = _loaded_controller(3)
        ctrl.remove_track(1)
        assert ctrl.get_track_count() == 2

    def test_remove_track_correct_element(self):
        ctrl = _loaded_controller(3)
        ctrl.remove_track(1)  # remove Track 2
        ids = [t['id'] for t in ctrl.get_queue()]
        assert 2 not in ids

    def test_remove_invalid_index_returns_false(self):
        ctrl = _loaded_controller(2)
        assert ctrl.remove_track(99) is False

    def test_remove_track_adjusts_current_index_when_before_current(self):
        ctrl = _loaded_controller(3)
        ctrl.current_index = 2  # pointing at Track 3
        ctrl.remove_track(0)    # remove Track 1 (before current)
        assert ctrl.current_index == 1

    def test_remove_current_track_stays_in_bounds(self):
        ctrl = _loaded_controller(3)
        ctrl.current_index = 2  # last track
        ctrl.remove_track(2)
        assert ctrl.current_index == 1  # clamped to new last


# ---------------------------------------------------------------------------
# clear / clear_queue
# ---------------------------------------------------------------------------

class TestClear:
    def test_clear_queue_empties_tracks(self):
        ctrl = _loaded_controller(5)
        ctrl.clear_queue()
        assert ctrl.is_queue_empty()

    def test_clear_resets_current_index(self):
        ctrl = _loaded_controller(3)
        ctrl.clear_queue()
        assert ctrl.current_index == -1

    def test_clear_alias_works(self):
        ctrl = _loaded_controller(3)
        ctrl.clear()
        assert ctrl.is_queue_empty()


# ---------------------------------------------------------------------------
# get_queue_info / is_queue_empty / get_track_count / get_queue_size
# ---------------------------------------------------------------------------

class TestQueueInfo:
    def test_is_queue_empty_true_on_new_controller(self):
        ctrl, _ = _make_controller()
        assert ctrl.is_queue_empty() is True

    def test_is_queue_empty_false_after_add(self):
        ctrl, _ = _make_controller()
        ctrl.add_track(_track(1))
        assert ctrl.is_queue_empty() is False

    def test_get_track_count_matches_added(self):
        ctrl = _loaded_controller(4)
        assert ctrl.get_track_count() == 4

    def test_get_queue_size_alias(self):
        ctrl = _loaded_controller(3)
        assert ctrl.get_queue_size() == ctrl.get_track_count()

    def test_get_queue_info_fields(self):
        ctrl = _loaded_controller(3)
        info = ctrl.get_queue_info()
        assert 'tracks' in info
        assert 'current_index' in info
        assert 'current_track' in info
        assert 'track_count' in info
        assert 'has_next' in info
        assert 'has_previous' in info
        assert 'shuffle_enabled' in info
        assert 'repeat_enabled' in info

    def test_get_queue_info_has_next_when_not_at_end(self):
        ctrl = _loaded_controller(3)
        ctrl.current_index = 0
        assert ctrl.get_queue_info()['has_next'] is True

    def test_get_queue_info_no_next_at_last(self):
        ctrl = _loaded_controller(3)
        ctrl.current_index = 2
        assert ctrl.get_queue_info()['has_next'] is False

    def test_get_queue_info_has_previous_when_not_at_start(self):
        ctrl = _loaded_controller(3)
        ctrl.current_index = 1
        assert ctrl.get_queue_info()['has_previous'] is True

    def test_get_queue_info_no_previous_at_start(self):
        ctrl = _loaded_controller(3)
        ctrl.current_index = 0
        assert ctrl.get_queue_info()['has_previous'] is False

    def test_get_queue_returns_copy(self):
        ctrl = _loaded_controller(2)
        q1 = ctrl.get_queue()
        q2 = ctrl.get_queue()
        assert q1 is not q2


# ---------------------------------------------------------------------------
# Library-backed methods (mocked repos)
# ---------------------------------------------------------------------------

class TestAddTrackFromLibrary:
    def test_returns_true_on_success(self):
        ctrl, factory = _make_controller()
        mock_track = MagicMock()
        mock_track.to_dict.return_value = _track(42)
        factory.tracks.get_by_id.return_value = mock_track

        result = ctrl.add_track_from_library(42)

        assert result is True
        assert ctrl.get_track_count() == 1

    def test_adds_correct_track(self):
        ctrl, factory = _make_controller()
        mock_track = MagicMock()
        mock_track.to_dict.return_value = _track(7)
        factory.tracks.get_by_id.return_value = mock_track

        ctrl.add_track_from_library(7)

        assert ctrl.get_queue()[0]['id'] == 7

    def test_returns_false_when_track_not_found(self):
        ctrl, factory = _make_controller()
        factory.tracks.get_by_id.return_value = None

        result = ctrl.add_track_from_library(999)

        assert result is False
        assert ctrl.is_queue_empty()

    def test_returns_false_on_repo_exception(self):
        ctrl, factory = _make_controller()
        factory.tracks.get_by_id.side_effect = RuntimeError("DB error")

        result = ctrl.add_track_from_library(1)

        assert result is False


class TestSearchAndAdd:
    def test_returns_count_of_added_tracks(self):
        ctrl, factory = _make_controller()
        mock_tracks = [MagicMock() for _ in range(3)]
        for i, t in enumerate(mock_tracks):
            t.to_dict.return_value = _track(i + 1)
        factory.tracks.search.return_value = (mock_tracks, 3)

        count = ctrl.search_and_add("jazz")

        assert count == 3
        assert ctrl.get_track_count() == 3

    def test_returns_zero_on_exception(self):
        ctrl, factory = _make_controller()
        factory.tracks.search.side_effect = RuntimeError("DB error")

        count = ctrl.search_and_add("jazz")

        assert count == 0
        assert ctrl.is_queue_empty()


class TestLoadPlaylist:
    def _make_playlist_mock(self, name: str, n_tracks: int) -> MagicMock:
        playlist = MagicMock()
        playlist.name = name
        playlist.tracks = [MagicMock() for _ in range(n_tracks)]
        for i, t in enumerate(playlist.tracks):
            t.to_dict.return_value = _track(i + 1)
        return playlist

    def test_returns_true_on_success(self):
        ctrl, factory = _make_controller()
        factory.playlists.get_by_id.return_value = self._make_playlist_mock("Rock", 3)

        result = ctrl.load_playlist(1)

        assert result is True

    def test_loads_all_tracks(self):
        ctrl, factory = _make_controller()
        factory.playlists.get_by_id.return_value = self._make_playlist_mock("Jazz", 4)

        ctrl.load_playlist(1)

        assert ctrl.get_track_count() == 4

    def test_replaces_existing_queue(self):
        ctrl, factory = _make_controller()
        ctrl.add_tracks([_track(i) for i in range(10)])
        factory.playlists.get_by_id.return_value = self._make_playlist_mock("New", 2)

        ctrl.load_playlist(1)

        assert ctrl.get_track_count() == 2

    def test_sets_start_index(self):
        ctrl, factory = _make_controller()
        factory.playlists.get_by_id.return_value = self._make_playlist_mock("Playlist", 5)

        ctrl.load_playlist(1, start_index=2)

        assert ctrl.current_index == 2

    def test_clamps_start_index(self):
        ctrl, factory = _make_controller()
        factory.playlists.get_by_id.return_value = self._make_playlist_mock("Playlist", 3)

        ctrl.load_playlist(1, start_index=99)

        assert ctrl.current_index == 2

    def test_returns_false_when_playlist_not_found(self):
        ctrl, factory = _make_controller()
        factory.playlists.get_by_id.return_value = None

        result = ctrl.load_playlist(999)

        assert result is False

    def test_returns_false_on_exception(self):
        ctrl, factory = _make_controller()
        factory.playlists.get_by_id.side_effect = RuntimeError("DB error")

        result = ctrl.load_playlist(1)

        assert result is False

    def test_returns_false_for_empty_playlist(self):
        ctrl, factory = _make_controller()
        factory.playlists.get_by_id.return_value = self._make_playlist_mock("Empty", 0)

        result = ctrl.load_playlist(1)

        assert result is False
