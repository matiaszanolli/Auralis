"""
Regression test: player load path traversal prevention (#2375, #2236)

Verifies that the /api/player/load endpoint validates track_id through
database lookup instead of accepting raw file paths, preventing path
traversal attacks like ../../../etc/passwd.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))


class TestPathTraversalPrevention:
    """Regression: player load must use database-validated paths (#2236)."""

    def test_load_track_uses_database_lookup(self):
        """load_track must query track from database by ID, not accept raw paths."""
        from routers.player import load_track
        source = inspect.getsource(load_track)

        # Must use tracks.get_by_id() for validation
        assert "library_database.tracks.get_by_id" in source, (
            "load_track must validate track via database get_by_id()"
        )

    def test_load_track_uses_validated_filepath(self):
        """load_track must use track.filepath from DB, not request.filepath."""
        from routers.player import load_track
        source = inspect.getsource(load_track)

        # Must reference track.filepath (from DB)
        assert "track.filepath" in source, (
            "load_track must use validated filepath from database record"
        )

    def test_broadcast_omits_filepath(self):
        """WebSocket broadcast must not leak server filesystem paths (#2479)."""
        from routers.player import load_track
        source = inspect.getsource(load_track)

        broadcast_source = source[
            source.index("connection_manager.broadcast"):
            source.index("background_tasks.add_task")
        ]
        assert '"track_id"' in broadcast_source or "'track_id'" in broadcast_source, (
            "Broadcast must use track_id to avoid leaking filesystem layout"
        )
        assert "filepath" not in broadcast_source

    def test_load_track_request_requires_track_id(self):
        """LoadTrackRequest schema must require track_id field."""
        from routers.player import LoadTrackRequest

        # Check that track_id is a required field
        assert "track_id" in LoadTrackRequest.model_fields
        assert LoadTrackRequest.model_fields["track_id"].is_required()
