"""Track list payloads carry no lyrics/comments text (#5906).

`Track.to_dict()` put the two largest text columns on every row of every list
page, album-tracks response and playlist detail, though the only reader of
lyrics is `GET /api/library/tracks/{id}/lyrics` and the frontend transformer
discards both fields. List reads also no longer pull them out of SQLite.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import event

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.tracks import get_track_lyrics, get_tracks  # noqa: E402
from schemas import TrackResponse  # noqa: E402

LYRICS = "[00:00.00]" + "la " * 2000


def _seed(track_repository) -> int:
    track = track_repository.add({
        'title': 'Lyric Track',
        'filepath': '/tmp/lyric_track_5906.wav',
        'duration': 100.0,
        'sample_rate': 44100,
        'channels': 2,
        'format': 'WAV',
        'artists': ['Lyric Artist'],
        'album': 'Lyric Album',
        'comments': 'a long comment',
    })
    assert track is not None
    # add() leaves lyrics to the lazy extraction path, so write them directly.
    assert track_repository.update_metadata(track.id, lyrics=LYRICS) is not None
    return track.id


def test_to_dict_has_no_lyrics_or_comments(track_repository):
    track_id = _seed(track_repository)

    track = track_repository.get_by_id(track_id)

    assert 'lyrics' not in track.to_dict()
    assert 'comments' not in track.to_dict()
    assert 'lyrics' not in TrackResponse.model_fields
    assert 'comments' not in TrackResponse.model_fields


def test_list_reads_do_not_select_the_text_columns(track_repository):
    _seed(track_repository)
    session = track_repository.get_session()
    try:
        engine = session.get_bind()
    finally:
        session.close()

    statements: list[str] = []

    def record(conn, cursor, statement, *rest):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        track_repository.get_all()
        track_repository.search('Lyric')
        track_repository.get_recent()
        track_repository.get_favorites()
        track_repository.get_by_artist('Lyric Artist')
    finally:
        event.remove(engine, "before_cursor_execute", record)

    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert selects
    leaked = [s for s in selects if 'tracks.lyrics' in s or 'tracks.comments' in s]
    assert not leaked, leaked


def test_single_track_read_still_carries_lyrics(track_repository):
    track = track_repository.get_by_id(_seed(track_repository))

    assert track.lyrics == LYRICS
    assert track.comments == 'a long comment'


def test_tracks_endpoint_rows_have_no_lyrics_key(track_repository):
    _seed(track_repository)
    repos = MagicMock()
    repos.tracks = track_repository

    payload = asyncio.run(get_tracks(limit=10, offset=0, search=None, order_by='created_at', repos=repos))

    assert payload['tracks']
    for row in payload['tracks']:
        assert 'lyrics' not in row
        assert 'comments' not in row


def test_lyrics_endpoint_still_returns_the_text(track_repository):
    track_id = _seed(track_repository)
    repos = MagicMock()
    repos.tracks = track_repository

    payload = asyncio.run(get_track_lyrics(track_id=track_id, repos=repos))

    assert payload["lyrics"] == LYRICS
    assert payload["format"] == "lrc"
