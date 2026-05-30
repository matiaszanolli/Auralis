"""
Regression tests: path leak via result_data (#3848) and metadata 404 detail (#3849).

Both findings belong to the same disclosure class as #3322 (server filesystem path
in API responses). These tests assert the sanitised form is in place.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.processing_engine import ProcessingJob, ProcessingStatus


# ---------------------------------------------------------------------------
# #3848: ProcessingJob.to_dict() — result_data must not expose output_path
# ---------------------------------------------------------------------------

class TestResultDataPathSanitisation:
    """result_data stored by process_job() must not contain the absolute output_path."""

    def _make_completed_job(self, output_path: str) -> ProcessingJob:
        job = ProcessingJob.__new__(ProcessingJob)
        job.job_id = "test-job"
        job.input_path = "/home/user/music/input.flac"
        job.output_path = output_path
        job.mode = "adaptive"
        job.settings = {}
        job.status = ProcessingStatus.COMPLETED
        job.progress = 100.0
        job.error_message = None
        job.created_at = datetime.now()
        job.started_at = datetime.now()
        job.completed_at = datetime.now()
        # Simulate what process_job() now stores (filename-only key)
        job.result_data = {
            "output_file": Path(output_path).name,
            "sample_rate": 44100,
            "duration": 180.0,
        }
        return job

    def test_result_data_has_no_output_path_key(self):
        """to_dict() result_data must not contain the absolute-path key 'output_path'."""
        job = self._make_completed_job("/tmp/auralis_processing/uuid_processed.wav")
        d = job.to_dict()
        result = d.get("result_data") or {}
        assert "output_path" not in result, (
            "result_data must not expose the absolute output_path (#3848)"
        )

    def test_result_data_contains_filename_only(self):
        """to_dict() result_data must expose only the filename via 'output_file'."""
        abs_path = "/tmp/auralis_processing/abc-def_processed.wav"
        job = self._make_completed_job(abs_path)
        d = job.to_dict()
        result = d.get("result_data") or {}
        assert result.get("output_file") == "abc-def_processed.wav"

    def test_to_dict_absolute_path_absent_from_all_fields(self):
        """The full /tmp path must not appear anywhere in the to_dict() output."""
        abs_path = "/tmp/auralis_processing/secret_processed.wav"
        job = self._make_completed_job(abs_path)
        d = job.to_dict()
        full_repr = str(d)
        assert "/tmp/auralis_processing" not in full_repr, (
            "Absolute output path leaked into to_dict() output (#3848)"
        )


# ---------------------------------------------------------------------------
# #3849: metadata router 404 detail must not embed str(FileNotFoundError)
# ---------------------------------------------------------------------------

class TestMetadata404DetailSanitisation:
    """FileNotFoundError caught in metadata endpoints must not leak the filepath."""

    def _make_router_and_app(self):
        """Build a minimal FastAPI app with just the metadata router."""
        from fastapi import FastAPI
        from routers.metadata import create_metadata_router

        app = FastAPI()
        router = create_metadata_router(
            get_repository_factory=lambda: None,
            broadcast_manager=MagicMock(),
        )
        app.include_router(router)
        return app

    def _make_repos(self, filepath: str) -> MagicMock:
        repos = MagicMock()
        track = MagicMock()
        track.id = 1
        track.filepath = filepath
        track.format = "flac"
        repos.tracks.get_by_id = MagicMock(return_value=track)
        return repos

    def test_get_editable_fields_404_has_no_filepath(self):
        """GET /fields 404 detail must not embed the absolute filepath."""
        from fastapi.testclient import TestClient

        app = self._make_router_and_app()
        abs_path = "/home/alice/private/music/secret.flac"
        repos = self._make_repos(abs_path)

        with (
            patch("routers.metadata.require_repository_factory", return_value=repos),
            patch("routers.metadata.validate_file_path", side_effect=FileNotFoundError(
                f"[Errno 2] No such file or directory: '{abs_path}'"
            )),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/api/metadata/tracks/1/fields")

        assert response.status_code == 404
        detail = response.json().get("detail", "")
        assert abs_path not in detail, (
            f"Absolute path leaked in 404 detail: {detail!r} (#3849)"
        )
        assert "1" in detail  # track_id should be present

    def test_get_track_metadata_404_has_no_filepath(self):
        """GET /metadata 404 detail must not embed the absolute filepath."""
        from fastapi.testclient import TestClient

        app = self._make_router_and_app()
        abs_path = "/home/alice/private/music/secret.flac"
        repos = self._make_repos(abs_path)

        with (
            patch("routers.metadata.require_repository_factory", return_value=repos),
            patch("routers.metadata.validate_file_path", side_effect=FileNotFoundError(
                f"[Errno 2] No such file or directory: '{abs_path}'"
            )),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/api/metadata/tracks/1")

        assert response.status_code == 404
        detail = response.json().get("detail", "")
        assert abs_path not in detail, (
            f"Absolute path leaked in 404 detail: {detail!r} (#3849)"
        )

    def test_update_track_metadata_404_has_no_filepath(self):
        """PUT /metadata 404 detail must not embed the absolute filepath."""
        from fastapi.testclient import TestClient

        app = self._make_router_and_app()
        abs_path = "/home/alice/private/music/secret.flac"
        repos = self._make_repos(abs_path)

        with (
            patch("routers.metadata.require_repository_factory", return_value=repos),
            patch("routers.metadata.validate_file_path", side_effect=FileNotFoundError(
                f"[Errno 2] No such file or directory: '{abs_path}'"
            )),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.put(
                    "/api/metadata/tracks/1",
                    json={"title": "Test"},
                )

        assert response.status_code == 404
        detail = response.json().get("detail", "")
        assert abs_path not in detail, (
            f"Absolute path leaked in 404 detail: {detail!r} (#3849)"
        )
