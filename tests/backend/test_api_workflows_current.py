"""Multi-step REST workflows against the live app and an isolated library (#5685).

tests/integration/test_api_workflows.py held twenty workflows that skipped unconditionally: their fixture
predated the component registry (#4670) and LibraryManager's removal (#4915), and they called endpoints that
no longer exist (/api/player/play/{id}, /api/player/status's old shape, a /api/library/search). They never
ran against any API built in months. These are the same intents written against the routes that exist now:
each test drives several requests in sequence and checks that a later read reflects an earlier write.

Per-endpoint behaviour is covered router by router elsewhere in tests/backend; what is checked here is that
the calls compose.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest
import soundfile as sf

ORIGIN = {"origin": "http://localhost:8765"}  # OriginCheckMiddleware rejects state changes without one (#4893)


def _write(client, method, url, **kwargs):
    headers = {**ORIGIN, **kwargs.pop("headers", {})}
    return getattr(client, method)(url, headers=headers, **kwargs)


@pytest.fixture
def three_tracks(client, tmp_path):
    """Three real library tracks over two albums, removed afterwards."""
    from main import globals_dict

    tracks = globals_dict["library_database"].tracks
    added = []
    for n in range(3):
        path = tmp_path / f"workflow_{n}.wav"
        sf.write(str(path), np.zeros((4410, 2), dtype=np.float32), 44100)
        track = tracks.add({
            "title": f"Workflow Track {n}", "filepath": str(path), "artists": [f"Workflow Artist {n}"],
            "album": f"Workflow Album {n % 2}", "format": "WAV", "sample_rate": 44100, "channels": 2,
            "duration": 0.1,
        })
        assert track is not None
        added.append(track.id)
    yield added
    _write(client, "post", "/api/player/queue/clear")
    for track_id in added:
        tracks.delete(track_id)


# --- library ---------------------------------------------------------------------------------------

def test_a_track_is_listed_fetched_and_favourited_then_unfavourited(client, three_tracks):
    listed = client.get("/api/library/tracks?limit=100").json()
    assert set(three_tracks) <= {t["id"] for t in listed["tracks"]}

    one = client.get(f"/api/library/tracks/{three_tracks[0]}").json()
    assert one["title"] == "Workflow Track 0"
    assert one["artists"] == ["Workflow Artist 0"]

    assert _write(client, "post", f"/api/library/tracks/{three_tracks[0]}/favorite").json()["favorite"] is True
    favourites = client.get("/api/library/tracks/favorites").json()["tracks"]
    assert three_tracks[0] in {t["id"] for t in favourites}

    assert _write(client, "delete", f"/api/library/tracks/{three_tracks[0]}/favorite").json()["favorite"] is False
    favourites = client.get("/api/library/tracks/favorites").json()["tracks"]
    assert three_tracks[0] not in {t["id"] for t in favourites}


def test_browsing_from_a_track_to_its_album_and_artist(client, three_tracks):
    track = client.get(f"/api/library/tracks/{three_tracks[1]}").json()

    album = client.get(f"/api/albums/{track['album_id']}").json()
    assert album["title"] == "Workflow Album 1"

    album_tracks = client.get(f"/api/albums/{track['album_id']}/tracks").json()
    assert three_tracks[1] in {t["id"] for t in album_tracks["tracks"]}

    artists = client.get("/api/artists?limit=200").json()["artists"]
    mine = next(a for a in artists if a["name"] == "Workflow Artist 1")
    artist_tracks = client.get(f"/api/artists/{mine['id']}/tracks").json()
    assert [t["id"] for t in artist_tracks["tracks"]] == [three_tracks[1]]


def test_the_library_stats_follow_the_tracks(client, three_tracks):
    stats = client.get("/api/library/stats").json()

    assert stats["total_tracks"] >= 3
    assert stats["total_albums"] >= 2


# --- player queue and transport -----------------------------------------------------------------------

def test_a_queue_is_set_edited_and_read_back(client, three_tracks):
    a, b, c = three_tracks

    assert _write(client, "post", "/api/player/queue", json={"tracks": [a, b]}).status_code == 200
    assert [t["id"] for t in client.get("/api/player/queue").json()["tracks"]] == [a, b]

    assert _write(client, "post", "/api/player/queue/add-track", json={"track_id": c}).status_code == 200
    assert [t["id"] for t in client.get("/api/player/queue").json()["tracks"]] == [a, b, c]

    assert _write(client, "put", "/api/player/queue/move", json={"from_index": 2, "to_index": 0}).status_code == 200
    assert [t["id"] for t in client.get("/api/player/queue").json()["tracks"]] == [c, a, b]

    assert _write(client, "delete", "/api/player/queue/1").status_code == 200
    assert [t["id"] for t in client.get("/api/player/queue").json()["tracks"]] == [c, b]

    assert _write(client, "post", "/api/player/queue/clear").status_code == 200
    assert client.get("/api/player/queue").json()["tracks"] == []


def test_shuffle_and_repeat_modes_are_reported_by_the_queue(client, three_tracks):
    _write(client, "post", "/api/player/queue", json={"tracks": three_tracks})

    assert _write(client, "post", "/api/player/queue/repeat", json={"mode": "all"}).status_code == 200
    assert client.get("/api/player/queue").json()["repeat_mode"] == "all"

    assert _write(client, "post", "/api/player/queue/shuffle", json={"enabled": True}).status_code == 200
    queue = client.get("/api/player/queue").json()
    assert sorted(t["id"] for t in queue["tracks"]) == sorted(three_tracks), "shuffle must keep every track"


def test_the_volume_route_echoes_the_clamped_level_and_leaves_server_state_to_the_client(client):
    # Volume is a client-side concern (#3722): the route validates, clamps to 0-100 and broadcasts; the
    # server's own snapshot is not where the level lives.
    assert _write(client, "post", "/api/player/volume", json={"volume": 55}).json()["volume"] == 55
    assert _write(client, "post", "/api/player/volume", json={"volume": 500}).json()["volume"] == 100
    assert _write(client, "post", "/api/player/volume", json={"volume": -20}).json()["volume"] == 0
    assert _write(client, "post", "/api/player/volume", json={"volume": "loud"}).status_code == 422


def test_a_malformed_queue_body_is_rejected_and_the_queue_is_untouched(client, three_tracks):
    _write(client, "post", "/api/player/queue", json={"tracks": three_tracks[:2]})

    assert _write(client, "post", "/api/player/queue", json={"tracks": "not a list"}).status_code == 422

    assert [t["id"] for t in client.get("/api/player/queue").json()["tracks"]] == three_tracks[:2]


# --- playlists ------------------------------------------------------------------------------------------

def test_a_playlist_is_created_filled_reordered_trimmed_and_deleted(client, three_tracks):
    created = _write(client, "post", "/api/playlists", json={"name": "Workflow List", "description": "d"}).json()
    playlist_id = created["playlist"]["id"]
    try:
        added = _write(client, "post", f"/api/playlists/{playlist_id}/tracks", json={"track_ids": three_tracks})
        assert added.status_code == 200
        assert added.json()["added_count"] == 3

        fetched = client.get(f"/api/playlists/{playlist_id}").json()
        assert [t["id"] for t in fetched["tracks"]] == three_tracks

        removed = _write(client, "delete", f"/api/playlists/{playlist_id}/tracks/{three_tracks[1]}")
        assert removed.status_code == 200
        fetched = client.get(f"/api/playlists/{playlist_id}").json()
        assert [t["id"] for t in fetched["tracks"]] == [three_tracks[0], three_tracks[2]]
    finally:
        assert _write(client, "delete", f"/api/playlists/{playlist_id}").status_code == 200

    assert client.get(f"/api/playlists/{playlist_id}").status_code == 404


# --- enhancement ----------------------------------------------------------------------------------------

def test_enhancement_settings_round_trip_and_reject_unknown_presets(client):
    status = client.get("/api/player/enhancement/status").json()
    assert status["preset"] == "adaptive"

    assert _write(client, "post", "/api/player/enhancement/intensity", json={"intensity": 0.5}).status_code == 200
    assert client.get("/api/player/enhancement/status").json()["intensity"] == 0.5

    assert _write(client, "post", "/api/player/enhancement/preset", json={"preset": "nope"}).status_code == 422
    assert client.get("/api/player/enhancement/status").json()["preset"] == "adaptive"

    _write(client, "post", "/api/player/enhancement/intensity", json={"intensity": status["intensity"]})


def test_supported_audio_formats_are_advertised(client):
    formats = client.get("/api/audio/formats").json()

    assert ".wav" in formats["input_formats"]
    assert ".flac" in formats["output_formats"]
    assert 44100 in formats["sample_rates"]
