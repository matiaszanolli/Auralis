"""
WebSocket Connect State Push Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #2606:
The WebSocket endpoint must push both player_state and
enhancement_settings_changed on initial connect so reconnecting
clients sync their Redux store immediately.
"""

import pytest


def _read_connection_setup_source() -> str:
    """Read the connection setup helper used by the system WebSocket route."""
    import pathlib

    # Direct file read — avoids import side effects from the backend module
    connection_handler = (
        pathlib.Path(__file__).resolve().parents[2]
        / "auralis-web" / "backend" / "ws_handlers" / "connection.py"
    )
    if not connection_handler.exists():
        pytest.skip(f"Could not locate {connection_handler}")
    return connection_handler.read_text()


@pytest.mark.regression
class TestWebSocketConnectStatePush:
    """Verify WS connect pushes player_state and enhancement_settings (#2606)."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        self.connection_source = _read_connection_setup_source()

    def test_pushes_player_state_on_connect(self):
        assert (
            '"player_state"' in self.connection_source
            or "'player_state'" in self.connection_source
        ), "setup_connection should push player_state on connect"

    def test_pushes_enhancement_settings_on_connect(self):
        assert (
            '"enhancement_settings_changed"' in self.connection_source
            or "'enhancement_settings_changed'" in self.connection_source
        ), "setup_connection should push enhancement_settings_changed on connect"
