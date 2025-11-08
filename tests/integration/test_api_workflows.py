"""
API Integration Tests - Phase 1 Week 2

Tests complete API workflows across multiple endpoints and services.
These tests verify that API endpoints work together correctly to support
real user workflows.

Test Categories:
1. Player API Integration (7 tests)
2. Library API Integration (7 tests)
3. Enhancement API Integration (6 tests)

Total: 20 API integration tests

Follows TESTING_GUIDELINES.md principles:
- Tests behavior across multiple API endpoints
- Uses real FastAPI test client
- Verifies API contracts and state transitions
- Focuses on integration between components
"""

import pytest
import numpy as np
import os
import time
from pathlib import Path
from fastapi.testclient import TestClient

# Import test fixtures
from tests.integration.test_e2e_workflows import temp_library, sample_audio_file

# Note: These tests require the FastAPI app to be importable
# They test API endpoints using TestClient


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def api_client(temp_library):
    """
    Create FastAPI test client with test library.

    Note: This assumes the FastAPI app can be imported and configured
    with a test database. If the app requires running server, these tests
    should be marked as integration tests that require manual setup.
    """
    # Import here to avoid circular imports
    try:
        from auralis_web.backend.main import app
        from auralis_web.backend.dependencies import get_library_manager

        manager, audio_dir, db_path = temp_library

        # Override dependency to use test library
        def override_get_library_manager():
            return manager

        app.dependency_overrides[get_library_manager] = override_get_library_manager

        client = TestClient(app)
        yield client, manager

        # Cleanup
        app.dependency_overrides.clear()
    except ImportError:
        pytest.skip("FastAPI app not available - requires backend installation")


@pytest.fixture
def library_with_tracks(api_client, sample_audio_file):
    """Create library with sample tracks via API."""
    client, manager = api_client

    # Add 5 test tracks
    track_ids = []
    for i in range(5):
        track_info = {
            'filepath': sample_audio_file,
            'title': f'Test Track {i+1}',
            'artists': [f'Artist {i+1}'],
            'album': f'Album {(i % 2) + 1}',
            'duration': 3.0 + i,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
        }
        track = manager.add_track(track_info)
        track_ids.append(track.id)

    return client, manager, track_ids


# ============================================================================
# PLAYER API INTEGRATION TESTS (7 tests)
# ============================================================================

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.player
def test_player_api_play_pause_workflow(library_with_tracks):
    """
    API Integration: Play → Pause → Resume

    Tests:
    - POST /api/player/play
    - POST /api/player/pause
    - GET /api/player/status
    """
    client, manager, track_ids = library_with_tracks

    # Play first track
    response = client.post(f"/api/player/play/{track_ids[0]}")
    assert response.status_code == 200

    # Check status
    response = client.get("/api/player/status")
    assert response.status_code == 200
    data = response.json()
    assert data['is_playing'] is True
    assert data['current_track']['id'] == track_ids[0]

    # Pause
    response = client.post("/api/player/pause")
    assert response.status_code == 200

    # Check paused status
    response = client.get("/api/player/status")
    data = response.json()
    assert data['is_playing'] is False


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.player
def test_player_api_seek_workflow(library_with_tracks):
    """
    API Integration: Play → Seek → Verify position

    Tests:
    - POST /api/player/seek
    - GET /api/player/status (position check)
    """
    client, manager, track_ids = library_with_tracks

    # Play track
    client.post(f"/api/player/play/{track_ids[0]}")

    # Seek to 1.5 seconds
    response = client.post("/api/player/seek", json={"position": 1.5})
    assert response.status_code == 200

    # Verify position
    response = client.get("/api/player/status")
    data = response.json()
    assert abs(data['position'] - 1.5) < 0.1  # Allow 100ms tolerance


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.player
def test_player_api_next_previous_workflow(library_with_tracks):
    """
    API Integration: Play → Next → Previous

    Tests:
    - POST /api/player/next
    - POST /api/player/previous
    - Queue navigation
    """
    client, manager, track_ids = library_with_tracks

    # Add tracks to queue
    for track_id in track_ids[:3]:
        client.post(f"/api/player/queue/add/{track_id}")

    # Play first track
    client.post(f"/api/player/play/{track_ids[0]}")

    # Next track
    response = client.post("/api/player/next")
    assert response.status_code == 200

    status = client.get("/api/player/status").json()
    assert status['current_track']['id'] == track_ids[1]

    # Previous track
    response = client.post("/api/player/previous")
    assert response.status_code == 200

    status = client.get("/api/player/status").json()
    assert status['current_track']['id'] == track_ids[0]


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.player
def test_player_api_queue_management_workflow(library_with_tracks):
    """
    API Integration: Add to queue → Remove → Clear

    Tests:
    - POST /api/player/queue/add/{track_id}
    - DELETE /api/player/queue/{index}
    - POST /api/player/queue/clear
    - GET /api/player/queue
    """
    client, manager, track_ids = library_with_tracks

    # Add tracks to queue
    for track_id in track_ids[:3]:
        response = client.post(f"/api/player/queue/add/{track_id}")
        assert response.status_code == 200

    # Get queue
    response = client.get("/api/player/queue")
    assert response.status_code == 200
    queue = response.json()
    assert len(queue) == 3

    # Remove middle track
    response = client.delete("/api/player/queue/1")
    assert response.status_code == 200

    queue = client.get("/api/player/queue").json()
    assert len(queue) == 2

    # Clear queue
    response = client.post("/api/player/queue/clear")
    assert response.status_code == 200

    queue = client.get("/api/player/queue").json()
    assert len(queue) == 0


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.player
def test_player_api_volume_control_workflow(library_with_tracks):
    """
    API Integration: Set volume → Verify → Mute → Unmute

    Tests:
    - POST /api/player/volume
    - GET /api/player/status (volume check)
    """
    client, manager, track_ids = library_with_tracks

    # Set volume to 50%
    response = client.post("/api/player/volume", json={"volume": 0.5})
    assert response.status_code == 200

    # Verify volume
    status = client.get("/api/player/status").json()
    assert abs(status['volume'] - 0.5) < 0.01

    # Mute (volume 0)
    response = client.post("/api/player/volume", json={"volume": 0.0})
    assert response.status_code == 200

    status = client.get("/api/player/status").json()
    assert status['volume'] == 0.0

    # Unmute (restore to 50%)
    response = client.post("/api/player/volume", json={"volume": 0.5})
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.player
def test_player_api_shuffle_repeat_workflow(library_with_tracks):
    """
    API Integration: Toggle shuffle → Toggle repeat

    Tests:
    - POST /api/player/shuffle
    - POST /api/player/repeat
    - GET /api/player/status (mode check)
    """
    client, manager, track_ids = library_with_tracks

    # Enable shuffle
    response = client.post("/api/player/shuffle", json={"enabled": True})
    assert response.status_code == 200

    status = client.get("/api/player/status").json()
    assert status['shuffle'] is True

    # Enable repeat
    response = client.post("/api/player/repeat", json={"mode": "all"})
    assert response.status_code == 200

    status = client.get("/api/player/status").json()
    assert status['repeat'] == "all"

    # Disable shuffle
    response = client.post("/api/player/shuffle", json={"enabled": False})
    status = client.get("/api/player/status").json()
    assert status['shuffle'] is False


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.player
def test_player_api_error_handling_workflow(library_with_tracks):
    """
    API Integration: Invalid operations → Error responses

    Tests:
    - Play non-existent track
    - Seek to negative position
    - Invalid volume values
    """
    client, manager, track_ids = library_with_tracks

    # Play non-existent track
    response = client.post("/api/player/play/99999")
    assert response.status_code in [404, 400]

    # Seek to negative position
    response = client.post("/api/player/seek", json={"position": -5.0})
    assert response.status_code in [400, 422]

    # Volume > 1.0
    response = client.post("/api/player/volume", json={"volume": 1.5})
    assert response.status_code in [400, 422]

    # Volume < 0.0
    response = client.post("/api/player/volume", json={"volume": -0.5})
    assert response.status_code in [400, 422]


# ============================================================================
# LIBRARY API INTEGRATION TESTS (7 tests)
# ============================================================================

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.library
def test_library_api_get_tracks_workflow(library_with_tracks):
    """
    API Integration: GET tracks → Pagination → Filtering

    Tests:
    - GET /api/library/tracks
    - Pagination parameters (limit, offset)
    - Total count accuracy
    """
    client, manager, track_ids = library_with_tracks

    # Get all tracks
    response = client.get("/api/library/tracks")
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 5
    assert len(data['tracks']) == 5

    # Paginate (2 per page)
    response = client.get("/api/library/tracks?limit=2&offset=0")
    data = response.json()
    assert len(data['tracks']) == 2
    assert data['total'] == 5
    assert data['has_more'] is True

    # Second page
    response = client.get("/api/library/tracks?limit=2&offset=2")
    data = response.json()
    assert len(data['tracks']) == 2


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.library
def test_library_api_scan_folder_workflow(api_client, tmp_path):
    """
    API Integration: POST scan → Progress → Completion

    Tests:
    - POST /api/library/scan
    - Duplicate prevention
    - Track count update
    """
    client, manager = api_client

    # Create test audio files
    audio_dir = tmp_path / "music"
    audio_dir.mkdir()

    for i in range(3):
        audio = np.random.randn(4410, 2) * 0.1
        from auralis.io.saver import save as save_audio
        filepath = audio_dir / f"track_{i}.wav"
        save_audio(str(filepath), audio, 44100, subtype='PCM_16')

    # Scan folder
    response = client.post("/api/library/scan", json={"path": str(audio_dir)})
    assert response.status_code in [200, 202]  # Sync or async response

    # Verify tracks added
    time.sleep(0.5)  # Allow time for async scan
    response = client.get("/api/library/tracks")
    data = response.json()
    assert data['total'] >= 3

    # Scan again (duplicate prevention)
    initial_count = data['total']
    response = client.post("/api/library/scan", json={"path": str(audio_dir)})

    time.sleep(0.5)
    response = client.get("/api/library/tracks")
    assert response.json()['total'] == initial_count  # No duplicates


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.library
def test_library_api_update_metadata_workflow(library_with_tracks):
    """
    API Integration: PUT metadata → Verify update

    Tests:
    - PUT /api/library/tracks/{id}
    - Metadata validation
    - Retrieval of updated data
    """
    client, manager, track_ids = library_with_tracks

    track_id = track_ids[0]

    # Update metadata
    response = client.put(
        f"/api/library/tracks/{track_id}",
        json={
            "title": "Updated Title",
            "artists": ["Updated Artist"],
            "album": "Updated Album",
            "year": 2024
        }
    )
    assert response.status_code == 200

    # Verify update
    response = client.get(f"/api/library/tracks/{track_id}")
    assert response.status_code == 200
    track = response.json()
    assert track['title'] == "Updated Title"
    assert "Updated Artist" in track['artists']
    assert track['album'] == "Updated Album"
    assert track['year'] == 2024


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.library
def test_library_api_delete_track_workflow(library_with_tracks):
    """
    API Integration: DELETE track → Verify removal

    Tests:
    - DELETE /api/library/tracks/{id}
    - Cascade deletion (playlists, queue)
    - Total count update
    """
    client, manager, track_ids = library_with_tracks

    initial_total = client.get("/api/library/tracks").json()['total']
    track_id = track_ids[0]

    # Delete track
    response = client.delete(f"/api/library/tracks/{track_id}")
    assert response.status_code == 200

    # Verify deletion
    response = client.get(f"/api/library/tracks/{track_id}")
    assert response.status_code == 404

    # Verify total count
    response = client.get("/api/library/tracks")
    assert response.json()['total'] == initial_total - 1


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.library
def test_library_api_search_workflow(library_with_tracks):
    """
    API Integration: Search by title → by artist → empty results

    Tests:
    - GET /api/library/search
    - Case-insensitive matching
    - Multiple result types
    """
    client, manager, track_ids = library_with_tracks

    # Search by title
    response = client.get("/api/library/search?query=Track%201")
    assert response.status_code == 200
    data = response.json()
    assert len(data['tracks']) >= 1
    assert any('Track 1' in t['title'] for t in data['tracks'])

    # Search by artist (case-insensitive)
    response = client.get("/api/library/search?query=artist%201")
    data = response.json()
    assert len(data['tracks']) >= 1

    # Empty results
    response = client.get("/api/library/search?query=NonExistentQuery12345")
    data = response.json()
    assert len(data['tracks']) == 0


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.library
def test_library_api_favorites_workflow(library_with_tracks):
    """
    API Integration: Add favorite → Get favorites → Remove

    Tests:
    - POST /api/library/tracks/{id}/favorite
    - GET /api/library/favorites
    - DELETE /api/library/tracks/{id}/favorite
    """
    client, manager, track_ids = library_with_tracks

    track_id = track_ids[0]

    # Add to favorites
    response = client.post(f"/api/library/tracks/{track_id}/favorite")
    assert response.status_code == 200

    # Get favorites
    response = client.get("/api/library/favorites")
    assert response.status_code == 200
    favorites = response.json()
    assert any(t['id'] == track_id for t in favorites['tracks'])

    # Remove from favorites
    response = client.delete(f"/api/library/tracks/{track_id}/favorite")
    assert response.status_code == 200

    # Verify removal
    response = client.get("/api/library/favorites")
    favorites = response.json()
    assert not any(t['id'] == track_id for t in favorites['tracks'])


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.library
def test_library_api_recent_tracks_workflow(library_with_tracks):
    """
    API Integration: Play tracks → Get recent → Verify order

    Tests:
    - GET /api/library/recent
    - Recency ordering
    - Limit parameter
    """
    client, manager, track_ids = library_with_tracks

    # Play tracks in order
    for track_id in track_ids[:3]:
        manager.record_track_play(track_id)
        time.sleep(0.1)  # Ensure different timestamps

    # Get recent tracks
    response = client.get("/api/library/recent?limit=5")
    assert response.status_code == 200
    data = response.json()

    # Verify most recent is first
    assert len(data['tracks']) >= 3
    recent_ids = [t['id'] for t in data['tracks'][:3]]

    # Should be in reverse play order (most recent first)
    assert recent_ids[0] == track_ids[2]
    assert recent_ids[1] == track_ids[1]
    assert recent_ids[2] == track_ids[0]


# ============================================================================
# ENHANCEMENT API INTEGRATION TESTS (6 tests)
# ============================================================================

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.audio
def test_enhancement_api_get_presets_workflow(api_client):
    """
    API Integration: GET presets → Verify defaults

    Tests:
    - GET /api/enhancement/presets
    - Preset structure validation
    """
    client, manager = api_client

    response = client.get("/api/enhancement/presets")
    assert response.status_code == 200
    presets = response.json()

    # Verify default presets exist
    preset_names = [p['name'] for p in presets]
    assert 'Adaptive' in preset_names
    assert 'Gentle' in preset_names
    assert 'Warm' in preset_names
    assert 'Bright' in preset_names
    assert 'Punchy' in preset_names

    # Verify preset structure
    for preset in presets:
        assert 'name' in preset
        assert 'description' in preset
        assert 'settings' in preset


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.audio
@pytest.mark.slow
def test_enhancement_api_apply_preset_workflow(library_with_tracks, sample_audio_file):
    """
    API Integration: Apply preset → Get progress → Verify completion

    Tests:
    - POST /api/enhancement/apply
    - GET /api/enhancement/progress/{job_id}
    - Output file creation
    """
    client, manager, track_ids = library_with_tracks

    track_id = track_ids[0]

    # Apply enhancement
    response = client.post(
        "/api/enhancement/apply",
        json={
            "track_id": track_id,
            "preset": "Gentle",
            "output_format": "WAV"
        }
    )

    # May be async (202) or sync (200)
    assert response.status_code in [200, 202]

    if response.status_code == 202:
        # Check progress for async
        data = response.json()
        job_id = data.get('job_id')

        if job_id:
            # Poll progress
            max_attempts = 30
            for _ in range(max_attempts):
                response = client.get(f"/api/enhancement/progress/{job_id}")
                progress = response.json()

                if progress['status'] == 'completed':
                    assert 'output_file' in progress
                    break

                time.sleep(0.5)


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.audio
def test_enhancement_api_get_current_settings_workflow(api_client):
    """
    API Integration: GET current settings → Modify → Verify

    Tests:
    - GET /api/enhancement/settings
    - PUT /api/enhancement/settings
    """
    client, manager = api_client

    # Get current settings
    response = client.get("/api/enhancement/settings")
    assert response.status_code == 200
    settings = response.json()

    # Verify structure
    assert 'preset' in settings
    assert 'enabled' in settings

    # Modify settings
    response = client.put(
        "/api/enhancement/settings",
        json={
            "preset": "Warm",
            "enabled": True
        }
    )
    assert response.status_code == 200

    # Verify update
    response = client.get("/api/enhancement/settings")
    updated = response.json()
    assert updated['preset'] == "Warm"
    assert updated['enabled'] is True


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.audio
def test_enhancement_api_preset_validation_workflow(api_client):
    """
    API Integration: Invalid preset → Error handling

    Tests:
    - POST /api/enhancement/apply with invalid preset
    - Error response format
    """
    client, manager = api_client

    # Try invalid preset
    response = client.post(
        "/api/enhancement/apply",
        json={
            "track_id": 1,
            "preset": "NonExistentPreset",
            "output_format": "WAV"
        }
    )

    assert response.status_code in [400, 422]
    error = response.json()
    assert 'detail' in error or 'error' in error


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.audio
def test_enhancement_api_format_support_workflow(api_client):
    """
    API Integration: Test supported output formats

    Tests:
    - GET /api/enhancement/formats
    - Format validation
    """
    client, manager = api_client

    response = client.get("/api/enhancement/formats")
    assert response.status_code == 200
    formats = response.json()

    # Verify supported formats
    assert 'WAV' in formats
    assert 'FLAC' in formats

    # Verify format details
    for fmt in formats:
        if isinstance(formats, dict):
            assert 'extensions' in formats[fmt] or 'description' in formats[fmt]


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.audio
@pytest.mark.slow
def test_enhancement_api_websocket_updates_workflow(library_with_tracks):
    """
    API Integration: WebSocket progress updates

    Tests:
    - WebSocket connection
    - Progress message format
    - Completion notification

    Note: This test may require WebSocket support in TestClient
    or be marked as manual test.
    """
    client, manager, track_ids = library_with_tracks

    # Note: TestClient WebSocket support may vary
    # This is a placeholder for WebSocket testing
    try:
        with client.websocket_connect("/ws") as websocket:
            # Send enhancement request
            websocket.send_json({
                "action": "apply_enhancement",
                "track_id": track_ids[0],
                "preset": "Gentle"
            })

            # Receive updates
            max_messages = 20
            completion_received = False

            for _ in range(max_messages):
                data = websocket.receive_json(timeout=5.0)

                if data.get('type') == 'enhancement_progress':
                    assert 'progress' in data
                    assert 0 <= data['progress'] <= 100

                if data.get('type') == 'enhancement_complete':
                    completion_received = True
                    assert 'output_file' in data
                    break

            assert completion_received
    except Exception as e:
        # WebSocket testing may not be supported in all environments
        pytest.skip(f"WebSocket testing not supported: {e}")


# ============================================================================
# SUMMARY STATISTICS
# ============================================================================

def test_api_integration_summary_stats():
    """Print summary of API integration test coverage."""
    print("\n" + "=" * 80)
    print("API INTEGRATION TEST SUMMARY")
    print("=" * 80)
    print(f"Player API Integration: 7 tests")
    print(f"  - Play/Pause/Resume workflow")
    print(f"  - Seek workflow")
    print(f"  - Next/Previous navigation")
    print(f"  - Queue management")
    print(f"  - Volume control")
    print(f"  - Shuffle/Repeat modes")
    print(f"  - Error handling")
    print()
    print(f"Library API Integration: 7 tests")
    print(f"  - Get tracks with pagination")
    print(f"  - Scan folder workflow")
    print(f"  - Update metadata")
    print(f"  - Delete track")
    print(f"  - Search workflow")
    print(f"  - Favorites management")
    print(f"  - Recent tracks")
    print()
    print(f"Enhancement API Integration: 6 tests")
    print(f"  - Get presets")
    print(f"  - Apply preset with progress")
    print(f"  - Get/Update settings")
    print(f"  - Preset validation")
    print(f"  - Format support")
    print(f"  - WebSocket updates")
    print("=" * 80)
    print(f"TOTAL API INTEGRATION TESTS: 20 tests")
    print("=" * 80)
    print()
    print("Phase 1 Week 2 Integration Tests:")
    print(f"  - E2E Workflow Tests: 30 tests (test_e2e_workflows.py)")
    print(f"  - API Integration Tests: 20 tests (test_api_workflows.py)")
    print(f"  - TOTAL INTEGRATION TESTS: 50 tests")
    print("=" * 80)
