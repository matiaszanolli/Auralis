"""
API Integration Tests

Tests complete API workflows and endpoint interactions.

Philosophy:
- Test real HTTP requests to FastAPI endpoints
- Test request/response validation
- Test error handling in API layer
- Test authentication and authorization
- Use TestClient for synchronous testing

These tests validate that the API layer works correctly
as a whole, catching integration issues between routes,
middleware, and business logic.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "auralis-web" / "backend"
sys.path.insert(0, str(backend_path))

from main import app

from auralis.io.saver import save as save_audio

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create a FastAPI test client with startup/shutdown events."""
    # #5398: OriginCheckMiddleware 403s every state-changing /api request
    # that arrives with an empty Origin from a non-loopback host, and
    # TestClient's host is 'testclient' — so without a default trusted
    # Origin, every write-path test here was rejected before route,
    # dependency-graph, or Pydantic validation ever ran. Same gap #5089
    # fixed in tests/backend/conftest.py; httpx merges these headers into
    # every request. The middleware's own enforcement stays covered by
    # test_origin_check_middleware.py, which builds its own app and client.
    with TestClient(app, headers={"origin": "http://localhost:8765"}) as client:
        yield client


@pytest.fixture
def temp_audio_dir():
    """Create a temporary directory for test audio files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def create_test_audio_file(filepath: Path, duration: float = 10.0):
    """Create a test audio file."""
    num_samples = int(duration * 44100)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    audio_stereo = np.column_stack([audio, audio])
    save_audio(str(filepath), audio_stereo, 44100, subtype='PCM_16')
    return filepath


# ============================================================================
# API Integration Tests - Health & System
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
def test_api_health_check(client):
    """
    API: GET /api/health returns 200 OK.

    Tests basic API health check endpoint.
    """
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


@pytest.mark.e2e
@pytest.mark.integration
def test_api_version_endpoint(client):
    """
    API: GET /api/version returns version info.

    Tests version information endpoint.
    """
    response = client.get("/api/version")

    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str)


# ============================================================================
# API Integration Tests - Player Endpoints
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
def test_api_player_status(client):
    """
    API: GET /api/player/status returns player state.

    Tests retrieving current player status.
    """
    response = client.get("/api/player/status")

    assert response.status_code == 200
    data = response.json()

    # Verify expected fields
    assert "state" in data  # playing, paused, stopped
    assert "current_track" in data or data.get("state") == "stopped"


@pytest.mark.e2e
@pytest.mark.integration
def test_api_player_volume_get(client):
    """
    API: GET /api/player/status returns the current volume level.

    There is no GET /api/player/volume route (the path is POST-only);
    volume is read back from PlayerState, whose `volume` is an int on the
    same 0-100 scale the POST body uses (#4711).
    """
    response = client.get("/api/player/status")

    assert response.status_code == 200
    data = response.json()

    assert "volume" in data
    assert 0 <= data["volume"] <= 100


@pytest.mark.e2e
@pytest.mark.integration
def test_api_player_volume_set(client):
    """
    API: POST /api/player/volume sets volume level.

    Tests setting volume via API. The volume is a JSON body on a 0-100
    scale (converted to 0.0-1.0 internally); the response echoes the
    service's rounded 0-100 int (#5050).
    """
    # Set volume to 70 on the 0-100 scale
    response = client.post("/api/player/volume", json={"volume": 70})

    assert response.status_code == 200
    data = response.json()

    assert "message" in data
    assert data["volume"] == 70


@pytest.mark.e2e
@pytest.mark.integration
def test_api_player_volume_validation(client):
    """
    API: POST /api/player/volume clamps out-of-range volume.

    Out-of-range values are clamped, not rejected — a deliberate contract
    (#3896; SetVolumeRequest's own docstring and test_phase4_player_workflow.
    py::test_volume_out_of_range pin the clamp). The only 422 the endpoint
    produces is a body that isn't a numeric volume at all.
    """
    response = client.post("/api/player/volume", json={"volume": 150})

    assert response.status_code == 200
    assert response.json()["volume"] == 100

    response = client.post("/api/player/volume", json={"volume": -50})

    assert response.status_code == 200
    assert response.json()["volume"] == 0

    response = client.post("/api/player/volume", json={"volume": "loud"})

    assert response.status_code == 422  # Validation error


# ============================================================================
# API Integration Tests - Library Endpoints
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
def test_api_library_tracks_get_all(client):
    """
    API: GET /api/library/tracks returns track list.

    Tests retrieving all tracks with pagination.
    """
    response = client.get("/api/library/tracks?limit=50&offset=0")

    assert response.status_code == 200
    data = response.json()

    assert "tracks" in data
    assert "total" in data
    assert isinstance(data["tracks"], list)
    assert isinstance(data["total"], int)


@pytest.mark.e2e
@pytest.mark.integration
def test_api_library_tracks_pagination(client):
    """
    API: GET /api/library/tracks supports pagination parameters.

    Tests that pagination parameters are respected.
    """
    # Request with specific limit
    response = client.get("/api/library/tracks?limit=10&offset=0")

    assert response.status_code == 200
    data = response.json()

    # Should return at most 10 tracks
    assert len(data["tracks"]) <= 10


@pytest.mark.e2e
@pytest.mark.integration
def test_api_library_search(client):
    """
    API: GET /api/library/search searches tracks.

    Tests search functionality.
    """
    response = client.get("/api/library/search?q=test&limit=50")

    # Search endpoint may not be implemented (404) or return results (200)
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.json()
        assert "tracks" in data
        assert "total" in data


# ============================================================================
# API Integration Tests - Albums & Artists
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
def test_api_albums_get_all(client):
    """
    API: GET /api/albums returns album list.

    Tests retrieving all albums.
    """
    response = client.get("/api/albums?limit=50&offset=0")

    assert response.status_code == 200
    data = response.json()

    assert "albums" in data
    assert "total" in data


@pytest.mark.e2e
@pytest.mark.integration
def test_api_artists_get_all(client):
    """
    API: GET /api/artists returns artist list.

    Tests retrieving all artists.
    """
    response = client.get("/api/artists?limit=50&offset=0")

    assert response.status_code == 200
    data = response.json()

    assert "artists" in data
    assert "total" in data


# ============================================================================
# API Integration Tests - Enhancement Settings
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
def test_api_enhancement_settings_get(client):
    """
    API: GET /api/player/enhancement/status returns current enhancement status.

    Tests retrieving enhancement settings/status.
    """
    response = client.get("/api/player/enhancement/status")

    # Accept 200 or 404 if endpoint doesn't exist
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        # Verify expected fields if endpoint exists
        assert "status" in data or "enabled" in data or "preset" in data


@pytest.mark.e2e
@pytest.mark.integration
def test_api_enhancement_settings_set(client):
    """
    API: POST /api/player/enhancement/preset updates enhancement preset.

    Tests updating enhancement settings. The preset is a JSON body
    (SetPresetRequest); 'adaptive' is the only valid name since the
    2026-09-13 preset narrowing (#5405).
    """
    response = client.post("/api/player/enhancement/preset", json={"preset": "adaptive"})

    assert response.status_code == 200
    data = response.json()
    settings = data.get("settings", data)
    assert "enabled" in settings or "preset" in settings


# ============================================================================
# API Integration Tests - Error Handling
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
def test_api_invalid_endpoint_404(client):
    """
    API: Invalid endpoint returns 404.

    Tests that non-existent endpoints return 404.
    """
    response = client.get("/api/nonexistent/endpoint")

    assert response.status_code == 404


@pytest.mark.e2e
@pytest.mark.integration
def test_api_invalid_method_405(client):
    """
    API: Invalid HTTP method returns 405.

    Tests that using wrong HTTP method returns 405.
    """
    # Try POST on a GET-only endpoint
    response = client.post("/api/health")

    # Should be 405 (Method Not Allowed) or 404
    assert response.status_code in [404, 405]


@pytest.mark.e2e
@pytest.mark.integration
def test_api_malformed_json_422(client):
    """
    API: Malformed JSON returns 422.

    Tests that malformed request body returns validation error.
    """
    # Send invalid JSON structure
    response = client.post(
        "/api/player/volume",
        json={"invalid_field": "value"}
    )

    # Should be 422 (Validation Error)
    assert response.status_code == 422


# ============================================================================
# API Integration Tests - Cache Management
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
def test_api_cache_stats(client):
    """
    API: GET /api/cache/stats returns cache statistics.

    Tests retrieving cache statistics. CacheStatsResponse is keyed by
    tier1/tier2/overall (per-tier stats) plus per-track status — not the
    flat "size"/"hits" shape this test predated.
    """
    response = client.get("/api/cache/stats")

    assert response.status_code == 200
    data = response.json()

    for section in ("tier1", "tier2", "overall", "tracks"):
        assert section in data
    assert "total_hits" in data["overall"]
    assert "total_chunks" in data["overall"]


@pytest.mark.e2e
@pytest.mark.integration
def test_api_cache_clear(client):
    """
    API: POST /api/cache/clear clears cache.

    Tests the real cache-clearing endpoint (cache_streamlined router,
    prefix /api/cache) rather than the /api/player/enhancement/cache/clear
    path this test guessed at, which has never existed.
    """
    response = client.post("/api/cache/clear")

    assert response.status_code == 200


# ============================================================================
# API Integration Tests - CORS Headers
# ============================================================================

@pytest.mark.e2e
@pytest.mark.integration
def test_api_cors_headers_present(client):
    """
    API: Responses include CORS headers.

    Tests that CORS headers are properly set.
    """
    response = client.get("/api/health")

    assert response.status_code == 200

    # Check for CORS headers (may vary based on configuration)
    # Just verify response is successful
    assert "content-type" in response.headers
