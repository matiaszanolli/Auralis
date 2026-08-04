"""
Regression test for #4731
~~~~~~~~~~~~~~~~~~~~~~~~~~

``MetadataUpdateRequest`` names its fields after mutagen tag names (``track``,
``disc``, ``comment``); the Track DB columns are named differently
(``track_number``, ``disc_number``, ``comments``). Both the single-track and
batch metadata routes used to build their DB-write dict with a bare
``model_dump()`` (field names, not the DB-column aliases), so
``track_number``/``disc_number``/``comments`` were never in the dict the
repository saw and got silently dropped by ``_filter_metadata_fields``
(whose allowlist is keyed on column names) — the file write succeeded while
the DB write silently no-opped for those three fields.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def client(monkeypatch):
    """Fresh app with only the metadata router, real repos/editor mocked out."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    # Break circular import: routers -> services -> config -> routers.
    # monkeypatch.setitem so this stub doesn't leak into sys.modules for the
    # rest of the pytest session and break other files' real-app fixtures.
    if "config.routes" not in sys.modules:
        routes_stub = ModuleType("config.routes")
        routes_stub.setup_routers = lambda app: None
        monkeypatch.setitem(sys.modules, "config.routes", routes_stub)

    from routers.metadata import create_metadata_router

    mock_track = Mock()
    mock_track.id = 1
    mock_track.filepath = "/fake/path/song.mp3"
    mock_track.format = "mp3"

    mock_repos = Mock()
    mock_repos.tracks = Mock()
    mock_repos.tracks.get_by_id = Mock(return_value=mock_track)
    mock_repos.tracks.get_by_ids = Mock(return_value={1: mock_track})
    mock_repos.tracks.update_metadata = Mock(return_value=mock_track)
    mock_repos.tracks.update_metadata_batch = Mock(return_value=[1])

    mock_editor = MagicMock()
    mock_editor.write_metadata.return_value = True
    mock_editor.read_metadata.return_value = {"title": "T"}
    mock_editor.batch_update.return_value = {
        "total": 1,
        "successful": 1,
        "failed": 0,
        "rolled_back": False,
        "results": [
            {
                "track_id": 1,
                "success": True,
                # Echoed verbatim from the tag-named dict the router built —
                # this is exactly the shape that used to reach the DB layer
                # unmodified.
                "updates": {"track": 5, "disc": 1, "comment": "hello", "title": "T"},
            }
        ],
    }

    mock_broadcast = Mock()
    mock_broadcast.broadcast = AsyncMock()

    # validate_file_path is imported at module scope in routers.metadata,
    # so patching the bound name there takes effect immediately.
    monkeypatch.setattr("routers.metadata.validate_file_path", lambda p: Path(p))

    app = FastAPI()
    router = create_metadata_router(
        get_repository_factory=lambda: mock_repos,
        broadcast_manager=mock_broadcast,
        metadata_editor=mock_editor,
    )
    app.include_router(router)

    return TestClient(app), mock_repos, mock_editor


class TestSingleTrackColumnTranslation:
    """PUT /api/metadata/tracks/{track_id}"""

    def test_track_disc_comment_translated_to_db_columns(self, client):
        test_client, mock_repos, mock_editor = client

        response = test_client.put(
            "/api/metadata/tracks/1",
            json={"track": 5, "disc": 1, "comment": "hello", "title": "T"},
        )

        assert response.status_code == 200

        # The file write still gets tag names (mutagen expects 'track'/'disc').
        file_call_kwargs = mock_editor.write_metadata.call_args[0][1]
        assert file_call_kwargs == {"track": 5, "disc": 1, "comment": "hello", "title": "T"}

        # The DB write must see column names, not tag names.
        mock_repos.tracks.update_metadata.assert_called_once_with(
            1, track_number=5, disc_number=1, comments="hello", title="T"
        )


class TestBatchColumnTranslation:
    """POST /api/metadata/batch"""

    def test_track_disc_comment_translated_to_db_columns(self, client):
        test_client, mock_repos, mock_editor = client

        response = test_client.post(
            "/api/metadata/batch",
            json={
                "updates": [
                    {
                        "track_id": 1,
                        "metadata": {"track": 5, "disc": 1, "comment": "hello", "title": "T"},
                    }
                ]
            },
        )

        assert response.status_code == 200

        mock_repos.tracks.update_metadata_batch.assert_called_once()
        (db_updates,), _ = mock_repos.tracks.update_metadata_batch.call_args
        assert db_updates == [
            (1, {"track_number": 5, "disc_number": 1, "comments": "hello", "title": "T"})
        ]


class TestTagDictToDbColumnsHelper:
    """Direct unit coverage of the translation helper itself."""

    def test_maps_aliased_fields_and_passes_through_the_rest(self):
        from routers.metadata import _tag_dict_to_db_columns

        result = _tag_dict_to_db_columns(
            {"track": 5, "disc": 1, "comment": "hi", "artist": "Someone", "title": "T"}
        )

        assert result == {
            "track_number": 5,
            "disc_number": 1,
            "comments": "hi",
            "artist": "Someone",  # no Track column — passes through unchanged,
            "title": "T",         # dropped downstream by _filter_metadata_fields
        }

    def test_empty_dict_passthrough(self):
        from routers.metadata import _tag_dict_to_db_columns

        assert _tag_dict_to_db_columns({}) == {}
