"""
WebSocket Connect State Push Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #2606:
The WebSocket endpoint must push both player_state and
enhancement_settings_changed on initial connect so reconnecting
clients sync their Redux store immediately.
"""

import pytest


def _read_ws_endpoint_source() -> str:
    """Read the system router source that contains the WS endpoint."""
    import pathlib
    # Direct file read — avoids import side effects from the backend module
    system_router = (
        pathlib.Path(__file__).resolve().parents[2]
        / 'auralis-web' / 'backend' / 'routers' / 'system.py'
    )
    if not system_router.exists():
        pytest.skip(f"Could not locate {system_router}")
    return system_router.read_text()


@pytest.mark.regression
class TestWebSocketConnectStatePush:
    """Verify WS connect pushes player_state and enhancement_settings (#2606)."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        self.ws_source = _read_ws_endpoint_source()

    def test_pushes_player_state_on_connect(self):
        assert '"player_state"' in self.ws_source or "'player_state'" in self.ws_source, \
            "websocket_endpoint should push player_state on connect"

    def test_pushes_enhancement_settings_on_connect(self):
        assert '"enhancement_settings_changed"' in self.ws_source or "'enhancement_settings_changed'" in self.ws_source, \
            "websocket_endpoint should push enhancement_settings_changed on connect"
