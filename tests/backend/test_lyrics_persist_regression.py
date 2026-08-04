"""
Regression test for #4730
~~~~~~~~~~~~~~~~~~~~~~~~~~

``GET /api/library/tracks/{id}/lyrics`` used to persist a file-extracted
lyric via ``TrackRepository.update(track_id, lyrics=lyrics_text)`` — a
signature ``update()`` does not have (it only accepts a positional
``track_info: dict``). The resulting ``TypeError`` was swallowed by a broad
``except Exception`` and the endpoint fell through to returning
``lyrics: None`` even though extraction succeeded.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


class _FakeAudioFile:
    """Minimal mutagen-File stand-in: no `.tags`, so the route takes the
    generic `.get(...)` branch (not the MP4 or ID3/Vorbis branches)."""

    def get(self, key, default=None):
        if key == "LYRICS":
            return ["Extracted lyric text"]
        return default


@pytest.fixture
def client(monkeypatch):
    """Fresh app with only the tracks router, real repos mocked out."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    # Break circular import: routers -> services -> config -> routers.
    # monkeypatch.setitem so this stub doesn't leak into sys.modules for the
    # rest of the pytest session and break other files' real-app fixtures.
    if "config.routes" not in sys.modules:
        routes_stub = ModuleType("config.routes")
        routes_stub.setup_routers = lambda app: None
        monkeypatch.setitem(sys.modules, "config.routes", routes_stub)

    from routers.tracks import create_tracks_router

    mock_track = Mock()
    mock_track.id = 1
    mock_track.filepath = "/fake/path/song.mp3"
    mock_track.lyrics = None

    mock_repos = Mock()
    mock_repos.tracks = Mock()
    mock_repos.tracks.get_by_id = Mock(return_value=mock_track)
    mock_repos.tracks.update_metadata = Mock(return_value=mock_track)
    # The pre-#4730 call target — asserted un-called below so a regression
    # (reverting to the broken signature) fails loudly instead of silently.
    mock_repos.tracks.update = Mock(
        side_effect=TypeError("update() got an unexpected keyword argument 'lyrics'")
    )

    # validate_file_path is imported locally inside the route body on every
    # call, so patching the source module (not routers.tracks) is what
    # actually takes effect.
    import security.path_security as path_security
    monkeypatch.setattr(path_security, "validate_file_path", lambda p: Path(p))

    import mutagen
    monkeypatch.setattr(mutagen, "File", lambda path: _FakeAudioFile())

    app = FastAPI()
    router = create_tracks_router(get_repository_factory=lambda: mock_repos)
    app.include_router(router)

    return TestClient(app), mock_repos


class TestLyricsExtractionPersistence:
    """GET /api/library/tracks/{track_id}/lyrics"""

    def test_extracted_lyrics_returned_and_persisted_via_update_metadata(self, client):
        test_client, mock_repos = client

        response = test_client.get("/api/library/tracks/1/lyrics")

        assert response.status_code == 200
        data = response.json()
        assert data["lyrics"] == "Extracted lyric text"

        # Correct target: update_metadata's allowlist contains 'lyrics'.
        mock_repos.tracks.update_metadata.assert_called_once_with(1, lyrics="Extracted lyric text")
        # The broken pre-#4730 call target must never be used for this path.
        mock_repos.tracks.update.assert_not_called()

    def test_extraction_survives_persistence_failure(self, client):
        """A DB write failure must not discard lyrics already extracted in
        this request (#4730 acceptance criterion)."""
        test_client, mock_repos = client
        mock_repos.tracks.update_metadata.side_effect = RuntimeError("db unavailable")

        response = test_client.get("/api/library/tracks/1/lyrics")

        assert response.status_code == 200
        data = response.json()
        assert data["lyrics"] == "Extracted lyric text"
