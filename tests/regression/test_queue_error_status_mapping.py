"""
Regression: queue endpoints map service errors by exception TYPE, not substring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#4700 — `set_queue` decided its status with `400 if "valid" in str(e) else ...`.
None of the three service-outage messages raised by `QueueService.set_queue`
("Audio player not available", "Player state manager not available",
"Library manager not available") contains the substring `"valid"`, so every
genuine service-unavailable condition was reported as 400 Bad Request with a
flattened detail — while every sibling endpoint mapped the same conditions to
503. `remove_from_queue` and `add_track_to_queue` used the same sniffing and
landed on the right codes only by luck of the current wording.

These tests pin the mapping to the exception type so a message rewording can
never silently change a status code again.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


@pytest.fixture
def client():
    from main import app
    # Starlette's TestClient sends no Origin from host 'testclient', which the
    # #3845 origin check rejects with 403 before any handler runs. Port 8765
    # (the backend's own origin) is allowlisted in both dev and prod (#4781).
    return TestClient(app, headers={"origin": "http://localhost:8765"})


@pytest.fixture
def mock_queue_manager():
    queue_manager = Mock()
    queue_manager.get_queue_size.return_value = 3
    queue_manager.get_queue.return_value = [
        {"id": 1, "title": "Track 1", "filepath": "/path/1.wav"},
        {"id": 2, "title": "Track 2", "filepath": "/path/2.wav"},
        {"id": 3, "title": "Track 3", "filepath": "/path/3.wav"},
    ]
    queue_manager.remove_track.return_value = True
    queue_manager.reorder_tracks.return_value = True
    return queue_manager


class TestServiceErrorTypes:
    """The typed exceptions themselves stay ValueError-compatible."""

    def test_service_errors_subclass_value_error(self):
        from services.errors import (
            InvalidRequest,
            OperationFailed,
            ResourceNotFound,
            ServiceError,
            ServiceUnavailable,
        )

        for cls in (ServiceUnavailable, InvalidRequest, ResourceNotFound, OperationFailed):
            assert issubclass(cls, ServiceError)
            # Pre-existing `except ValueError` call sites must keep working.
            assert issubclass(cls, ValueError)

    @pytest.mark.parametrize("message", [
        "Audio player not available",
        "Player state manager not available",
        "Library manager not available",
    ])
    def test_outage_messages_do_not_contain_valid(self, message):
        """The exact reason the old substring check misfired."""
        assert "valid" not in message


class TestSetQueueStatusMapping:
    """POST /api/player/queue"""

    @pytest.mark.parametrize("missing", [
        "audio_player",
        "player_state_manager",
    ])
    def test_component_unavailable_returns_503(self, client, missing):
        """#4700: all three outage conditions were reported as 400."""
        globals_patch = {'audio_player': Mock(), 'player_state_manager': Mock()}
        globals_patch[missing] = None

        with patch.dict('main.globals_dict', globals_patch):
            response = client.post(
                "/api/player/queue",
                json={"tracks": [1, 2, 3], "start_index": 0},
            )

        assert response.status_code == 503, (
            f"missing {missing} is a service outage, not a client error"
        )
        # The operator-facing reason survives instead of being flattened
        # to a generic "Player not available".
        assert "not available" in response.json()['detail']

    def test_unresolvable_track_ids_still_return_400(self, client):
        """A genuinely bad request must stay a client error."""
        mock_player = Mock()
        mock_state = Mock()
        mock_library = Mock()
        mock_library.tracks.get_by_ids.return_value = {}

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': mock_state,
            'library_database': mock_library,
        }):
            response = client.post(
                "/api/player/queue",
                json={"tracks": [999999], "start_index": 0},
            )

        assert response.status_code == 400
        assert "No valid tracks found" in response.json()['detail']


class TestSiblingHandlerMapping:
    """The two handlers that were right only by luck of the current wording."""

    def test_remove_invalid_index_returns_400(self, client, mock_queue_manager):
        mock_player = Mock()
        mock_player.queue = mock_queue_manager

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': Mock(),
        }):
            response = client.delete("/api/player/queue/999")

        assert response.status_code == 400
        assert "Invalid index" in response.json()['detail']

    def test_remove_no_player_returns_503(self, client):
        with patch.dict('main.globals_dict', {'audio_player': None}):
            response = client.delete("/api/player/queue/0")

        assert response.status_code == 503

    def test_add_track_not_found_returns_404(self, client, mock_queue_manager):
        mock_player = Mock()
        mock_player.queue = mock_queue_manager
        mock_library = Mock()
        mock_library.tracks.get_by_id.return_value = None

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': Mock(),
            'library_database': mock_library,
        }):
            response = client.post(
                "/api/player/queue/add-track",
                json={"track_id": 999999},
            )

        assert response.status_code == 404

    def test_add_track_no_player_returns_503(self, client):
        with patch.dict('main.globals_dict', {'audio_player': None}):
            response = client.post(
                "/api/player/queue/add-track",
                json={"track_id": 1},
            )

        assert response.status_code == 503

    def test_reorder_component_unavailable_returns_503(self, client):
        """Previously 400: reorder mapped *every* ValueError to a client error."""
        with patch.dict('main.globals_dict', {'audio_player': None}):
            response = client.put(
                "/api/player/queue/reorder",
                json={"new_order": [0, 1, 2]},
            )

        assert response.status_code == 503

    def test_reorder_bad_order_still_returns_400(self, client, mock_queue_manager):
        mock_player = Mock()
        mock_player.queue = mock_queue_manager
        mock_ws = Mock()
        mock_ws.broadcast = AsyncMock()

        with patch.dict('main.globals_dict', {
            'audio_player': mock_player,
            'player_state_manager': Mock(),
        }), patch('main.manager', mock_ws):
            response = client.put(
                "/api/player/queue/reorder",
                json={"new_order": [0, 0, 0]},
            )

        assert response.status_code == 400

    def test_move_component_unavailable_returns_503(self, client):
        """Previously 400 for the same reason as reorder."""
        with patch.dict('main.globals_dict', {'audio_player': None}):
            response = client.put(
                "/api/player/queue/move",
                json={"from_index": 0, "to_index": 1},
            )

        assert response.status_code == 503


class TestNoSubstringSniffingRemains:
    """Acceptance criterion: no handler picks a status by matching message text."""

    def test_player_router_has_no_message_substring_checks(self):
        source = (
            Path(__file__).parent.parent.parent
            / "auralis-web" / "backend" / "routers" / "player.py"
        ).read_text()

        for pattern in ('"valid" in str(e)', '"Invalid" in str(e)', '"not found" in str(e)'):
            assert pattern not in source, (
                f"status code decided by substring match ({pattern}) — see #4700"
            )
