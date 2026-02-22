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

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))


class TestPathTraversalPrevention:
    """Regression: player load must use database-validated paths (#2236)."""

    def test_load_track_uses_database_lookup(self):
        """load_track must query track from database by ID, not accept raw paths."""
        from routers.player import PlayerRouter
        source = inspect.getsource(PlayerRouter)

        # Must use tracks.get_by_id() for validation
        assert "get_by_id" in source, (
            "load_track must validate track via database get_by_id()"
        )

    def test_load_track_uses_validated_filepath(self):
        """load_track must use track.filepath from DB, not request.filepath."""
        from routers.player import PlayerRouter
        source = inspect.getsource(PlayerRouter)

        # Must reference track.filepath (from DB)
        assert "track.filepath" in source, (
            "load_track must use validated filepath from database record"
        )

    def test_broadcast_omits_filepath(self):
        """WebSocket broadcast must not leak server filesystem paths (#2479)."""
        from routers.player import PlayerRouter
        source = inspect.getsource(PlayerRouter)

        # The broadcast should use track_id, not filepath
        assert '"track_id"' in source or "'track_id'" in source, (
            "Broadcast must use track_id to avoid leaking filesystem layout"
        )

    def test_load_track_request_requires_track_id(self):
        """LoadTrackRequest schema must require track_id field."""
        from schemas import LoadTrackRequest
        import inspect as _inspect
        # Check that track_id is a required field
        annotations = LoadTrackRequest.__annotations__ if hasattr(LoadTrackRequest, '__annotations__') else {}
        fields = LoadTrackRequest.model_fields if hasattr(LoadTrackRequest, 'model_fields') else {}

        has_track_id = 'track_id' in annotations or 'track_id' in fields
        assert has_track_id, "LoadTrackRequest must require track_id"
