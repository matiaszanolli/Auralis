"""Every paged ORDER BY ends in the model id (#5907).

#4796 gave only `TrackRepository.search()` an id tie-breaker. Offset
pagination over rows with equal sort keys (albums sharing a title, tracks
sharing a title in the favorites view, artists with equal counts) can
duplicate or skip rows at a page boundary unless the order is total.

SQLite happens to be stable for a fixed plan, so the tests assert the compiled
ORDER BY rather than relying on a plan-dependent paging result.
"""

import re

import pytest
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import Session


class _CapturingSession:
    """Delegates to a real session but records the statements it executes."""

    def __init__(self, session: Session, sink: list[str]):
        self._session = session
        self._sink = sink

    def execute(self, stmt, *args, **kwargs):
        self._sink.append(str(stmt.compile(dialect=sqlite.dialect())))
        return self._session.execute(stmt, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._session, name)


def _order_by_clauses(sql: str) -> list[str]:
    """ORDER BY terms of a compiled statement, minus LIMIT/OFFSET."""
    tail = sql.rsplit("ORDER BY", 1)[1]
    tail = tail.split("LIMIT")[0]
    return [t.strip() for t in tail.split(",")]


def _capture(repo, monkeypatch, call) -> list[str]:
    sink: list[str] = []
    original = repo._session_scope

    from contextlib import contextmanager

    @contextmanager
    def scope():
        with original() as session:
            yield _CapturingSession(session, sink)

    monkeypatch.setattr(repo, "_session_scope", scope)
    call()
    return [s for s in sink if "ORDER BY" in s and "LIMIT" in s]


@pytest.mark.parametrize("order_by", ["name", "album_count", "track_count"])
def test_artist_orders_end_in_id(artist_repository, monkeypatch, order_by):
    statements = _capture(
        artist_repository, monkeypatch,
        lambda: (
            artist_repository.get_all(order_by=order_by),
            artist_repository.search("x", order_by=order_by),
        ),
    )
    assert len(statements) == 2
    for sql in statements:
        # The tie-breaker follows the primary direction (#5868), so the
        # most-first count orders end in id DESC; either is a total order.
        assert _order_by_clauses(sql)[-1] in ("artists.id ASC", "artists.id DESC")


def test_album_pages_end_in_id(album_repository, monkeypatch):
    statements = _capture(
        album_repository, monkeypatch,
        lambda: (
            album_repository.get_all(),
            album_repository.search("x"),
            album_repository.get_recent(),
        ),
    )
    assert len(statements) == 3
    for sql in statements:
        assert _order_by_clauses(sql)[-1].startswith("albums.id")


def test_track_pages_end_in_id(track_repository, monkeypatch):
    statements = _capture(
        track_repository, monkeypatch,
        lambda: (
            track_repository.get_all(order_by="play_count"),
            track_repository.get_favorites(),
            track_repository.get_recent(),
        ),
    )
    assert len(statements) == 3
    for sql in statements:
        # Eager joins wrap the paged SELECT in a subquery, aliasing the table.
        assert re.fullmatch(r"(tracks|anon_\d+)\.id( ASC| DESC)?", _order_by_clauses(sql)[-1])


def test_playlist_page_ends_in_id(playlist_repository, monkeypatch):
    statements = _capture(
        playlist_repository, monkeypatch, lambda: playlist_repository.get_all()
    )
    assert len(statements) == 1
    assert _order_by_clauses(statements[0])[-1] == "playlists.id"


def test_albums_with_identical_titles_page_without_duplicates(track_repository, album_repository):
    for i in range(120):
        track_repository.add({
            'title': f'T{i}',
            'filepath': f'/tmp/dup_album_{i}.wav',
            'duration': 10.0,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': [f'Artist {i}'],
            'album': 'Greatest Hits',
        })

    seen: list[int] = []
    for offset in range(0, 120, 50):
        page, _ = album_repository.get_all(limit=50, offset=offset)
        seen.extend(a.id for a in page)

    assert len(seen) == len(set(seen))
