"""
Regression tests for #5171 — ``PlaylistRepository.search()``.

Playlist search was never implemented: not on ``PlaylistRepository``, and not
on the deprecated library facade that preceded it. ``db.playlists.search(...)``
had always raised ``AttributeError``, and the only test covering it lived in a
module-wide ``pytest.mark.skip``, so nothing surfaced the gap.

These tests pin the new method's contract, matching the peer repositories'
``search()``: ``(results, total)`` so callers can paginate, LIKE metacharacters
escaped so ``%`` is not a wildcard, and the same per-row aggregates ``get_all()``
attaches so a search hit serialises identically to a listed playlist.
"""

from __future__ import annotations

import pytest

from auralis.library.repositories.base import escape_like
from auralis.library.repositories.playlist_repository import PlaylistRepository


@pytest.fixture
def playlist_repo(session_factory):
    """Repository seeded with playlists whose names and descriptions differ."""
    repo = PlaylistRepository(session_factory)
    repo.create("Playlist 1", "Test playlist 1")
    repo.create("Playlist 2", "Test playlist 2")
    repo.create("Road Trip", "Songs for driving")
    repo.create("Focus", "instrumental playlist for work")
    return repo


def test_search_returns_matches_and_total(playlist_repo):
    results, total = playlist_repo.search("Playlist 1")

    assert total == 1
    assert [p.name for p in results] == ["Playlist 1"]


def test_search_is_case_insensitive(playlist_repo):
    results, total = playlist_repo.search("road trip")

    assert total == 1
    assert results[0].name == "Road Trip"


def test_search_matches_description_not_only_name(playlist_repo):
    """'instrumental' appears only in a description, never in a name."""
    results, total = playlist_repo.search("instrumental")

    assert total == 1
    assert results[0].name == "Focus"


def test_search_excludes_non_matching_playlists(playlist_repo):
    results, _ = playlist_repo.search("Playlist")

    names = {p.name for p in results}
    assert "Road Trip" not in names
    # "Focus" matches on its description ("... playlist for work"), which is
    # intended — substring search covers both columns.
    assert {"Playlist 1", "Playlist 2"} <= names


def test_search_with_no_matches_returns_empty(playlist_repo):
    results, total = playlist_repo.search("nonexistent playlist name")

    assert results == []
    assert total == 0


def test_search_escapes_like_wildcards(playlist_repo):
    """A bare '%' must match nothing, not every playlist (#2405's class)."""
    results, total = playlist_repo.search("%")

    assert total == 0
    assert results == []


def test_search_escapes_underscore_wildcard(playlist_repo):
    """'_' is LIKE's single-character wildcard; 'P_aylist' must not match."""
    _, total = playlist_repo.search("P_aylist")

    assert total == 0


def test_search_finds_literal_metacharacters(playlist_repo):
    """Escaping must not break searching for a real '%' in a name."""
    playlist_repo.create("100% Bangers", "")

    results, total = playlist_repo.search("100%")

    assert total == 1
    assert results[0].name == "100% Bangers"


def test_search_total_is_full_count_not_page_length(playlist_repo):
    """total must survive pagination — otherwise callers cannot page."""
    results, total = playlist_repo.search("Playlist", limit=1)

    assert len(results) == 1
    assert total >= 2


def test_search_pagination_does_not_overlap(playlist_repo):
    """Consecutive pages must be disjoint (stable ORDER BY, cf. #4796)."""
    page1, total = playlist_repo.search("Playlist", limit=1, offset=0)
    page2, _ = playlist_repo.search("Playlist", limit=1, offset=1)

    assert total >= 2
    assert page1[0].id != page2[0].id


def test_search_results_carry_track_count(playlist_repo, session_factory):
    """Search hits get get_all()'s aggregates, so to_dict() is not wrong."""
    from auralis.library.repositories.track_repository import TrackRepository

    track_repo = TrackRepository(session_factory)
    track = track_repo.add({
        'filepath': '/tmp/playlist_search_5171.flac',
        'title': 'Seeded Track',
        'artists': ['Artist'],
        'format': 'FLAC',
        'sample_rate': 44100,
        'channels': 2,
    })
    results, _ = playlist_repo.search("Road Trip")
    playlist_repo.add_track(results[0].id, track.id)

    results, _ = playlist_repo.search("Road Trip")
    assert results[0].to_dict()['track_count'] == 1


def test_escape_like_matches_the_inline_repository_expression():
    """The helper must be byte-identical to the copies it will replace."""
    for query in ('plain', '50%', 'a_b', r'back\slash', '%_\\'):
        inline = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        assert escape_like(query) == inline
