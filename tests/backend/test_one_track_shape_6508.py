"""A track's artists and album are described the same way by every payload (#6508).

Library responses sent `artists: list[str]` and a nullable album; queue/player/WS sent `artist` =
the first artist only, with "Unknown Artist"/"Unknown Album" sentinels; the fingerprint route sent
every artist joined, with the same sentinels. All three now come from player_state's
track_artist_names / track_album_title: every artist, a joined display string, and None for no
album. The labels are the frontend's (#5905).
"""

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(BACKEND))

from player_state import create_track_info, track_album_title, track_artist_names  # noqa: E402
from services.queue_enrichment import to_track_payload  # noqa: E402


def _track(artists, album):
    return SimpleNamespace(
        id=1, title="T", duration=60.0, filepath="/m/t.flac", format="flac", album_id=None,
        artists=[SimpleNamespace(name=n) for n in artists],
        album=SimpleNamespace(title=album, id=None, artwork_path=None) if album else None,
    )


@pytest.mark.parametrize("artists, album, joined", [
    (["A", "B"], "Record", "A, B"),
    ([], None, ""),
])
def test_queue_and_ws_payloads_carry_every_artist_and_a_nullable_album(artists, album, joined):
    track = _track(artists, album)

    info = create_track_info(track)
    payload = to_track_payload(info)

    assert info.artists == artists and payload["artists"] == artists
    assert info.artist == payload["artist"] == joined
    assert info.album == payload["album"] == album
    assert "Unknown" not in repr(payload)


def test_the_fingerprint_route_uses_the_same_helpers():
    tree = ast.parse((BACKEND / "routers" / "fingerprint_status.py").read_text())
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert {"track_artist_names", "track_album_title"} <= called
    assert "Unknown Artist" not in (BACKEND / "routers" / "fingerprint_status.py").read_text()


def test_the_helpers_accept_plain_strings_too():
    plain = SimpleNamespace(artist="Solo", album="")
    assert track_artist_names(plain) == ["Solo"]
    assert track_album_title(plain) is None
