"""Tests for TrackRepository.set_favorite's bool return / raise (#4763).

Previously set_favorite() returned None unconditionally and swallowed commit
failures, so POST/DELETE /api/library/tracks/{id}/favorite always reported
200 success even for a nonexistent track_id or a failed write. It now
returns True/False so callers can distinguish "not found" from "success",
and re-raises on commit failure instead of swallowing it.
"""

import pytest


def _add_track(track_repository, filepath="/music/set_favorite_test.flac"):
    track = track_repository.add({
        'title': 'Set Favorite Test',
        'filepath': filepath,
        'sample_rate': 44_100,
        'channels': 2,
        'format': 'FLAC',
    })
    assert track is not None
    return track


def test_set_favorite_returns_true_on_success(track_repository):
    track = _add_track(track_repository)

    result = track_repository.set_favorite(track.id, True)

    assert result is True
    fetched = track_repository.get_by_id(track.id)
    assert fetched.favorite is True


def test_set_favorite_returns_false_for_nonexistent_track(track_repository):
    result = track_repository.set_favorite(999_999, True)

    assert result is False


def test_set_favorite_unset_returns_true(track_repository):
    track = _add_track(track_repository)
    track_repository.set_favorite(track.id, True)

    result = track_repository.set_favorite(track.id, False)

    assert result is True
    fetched = track_repository.get_by_id(track.id)
    assert fetched.favorite is False


def test_set_favorite_reraises_on_commit_failure(track_repository, monkeypatch):
    """A commit failure must propagate, not be swallowed into a falsy
    success-looking return (#4763)."""
    track = _add_track(track_repository)

    session = track_repository.get_session()

    class _ExplodingSession:
        def execute(self, *args, **kwargs):
            return session.execute(*args, **kwargs)

        def commit(self):
            raise RuntimeError("simulated commit failure")

        def rollback(self):
            session.rollback()

        def close(self):
            session.close()

    monkeypatch.setattr(track_repository, "get_session", lambda: _ExplodingSession())

    with pytest.raises(RuntimeError, match="simulated commit failure"):
        track_repository.set_favorite(track.id, True)
