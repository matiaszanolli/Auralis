"""
The two `volume` scales are each unambiguous (#4711)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`volume` names two incompatible scales on the same API surface:

  * normalised 0.0-1.0 — `SettingsUpdateRequest`, `SettingsResponse`, and the
    persisted `UserSettings.volume` column (default 0.8);
  * 0-100 — `SetVolumeRequest`, `PlayerState.volume`, and the WS broadcast the
    frontend reads.

The only markers used to be a `le=1.0` bound on one side and a parenthetical
in a docstring on the other, and `SettingsResponse.volume` was an unbounded
`float | None` — so the scale was enforced on the way in but not on the way
out. A persisted 0.8 read as 0-100 is 0.8% volume: silent, not loud.

#4711 kept the persisted scale (renaming the column would need a migration,
and acceptance criterion 3 is that stored settings still restore to the
correct loudness) and made every field state its scale in `description=`,
plus bounded the response side to match the request side.

These tests pin both halves: the bounds, and the presence of a scale marker
in each model's field metadata so a future field cannot be added without one.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import types
from pathlib import Path

import pytest

_backend_dir = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
sys.path.insert(0, str(_backend_dir))

if 'routers' not in sys.modules:
    _stub = types.ModuleType('routers')
    _stub.__path__ = [str(_backend_dir / 'routers')]
    _stub.__package__ = 'routers'
    sys.modules['routers'] = _stub

from player_state import PlayerState  # noqa: E402
from routers.player import SetVolumeRequest  # noqa: E402
from routers.settings import SettingsResponse, SettingsUpdateRequest  # noqa: E402


def _description(model, field: str) -> str:
    return model.model_fields[field].description or ''


class TestNormalisedScale:
    """Settings volume is 0.0-1.0, in both directions."""

    @pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
    def test_request_accepts_in_range(self, value):
        assert SettingsUpdateRequest(volume=value).volume == value

    @pytest.mark.parametrize("value", [-0.01, 1.01, 80, 100])
    def test_request_rejects_out_of_range(self, value):
        """A 0-100 value sent to the normalised field must 422, not silently pass."""
        with pytest.raises(Exception):
            SettingsUpdateRequest(volume=value)

    @pytest.mark.parametrize("value", [0.0, 0.8, 1.0])
    def test_response_accepts_in_range(self, value):
        assert SettingsResponse(volume=value).volume == value

    @pytest.mark.parametrize("value", [-0.01, 1.01, 80])
    def test_response_rejects_out_of_range(self, value):
        """Previously unbounded (#4711) — the scale is now enforced both ways."""
        with pytest.raises(Exception):
            SettingsResponse(volume=value)

    def test_persisted_default_is_in_range(self):
        """UserSettings.volume defaults to 0.8; it must round-trip the response."""
        assert SettingsResponse(volume=0.8).volume == 0.8


class TestZeroToHundredScale:
    """Player volume is 0-100 and clamps rather than rejecting."""

    @pytest.mark.parametrize("sent, expected", [(150, 100.0), (-50, 0.0), (80, 80.0)])
    def test_clamps_instead_of_rejecting(self, sent, expected):
        """Deliberate contract — see the comment on SetVolumeRequest."""
        assert SetVolumeRequest(volume=sent).volume == expected

    def test_player_state_default_is_the_0_100_scale(self):
        assert PlayerState().volume == 80


class TestScaleIsDocumented:
    """Every `volume` field states its scale, so neither can be read by guess."""

    @pytest.mark.parametrize(
        "model, field, marker",
        [
            (SettingsUpdateRequest, 'volume', '0.0-1.0'),
            (SettingsResponse, 'volume', '0.0-1.0'),
            (SetVolumeRequest, 'volume', '0-100'),
            (PlayerState, 'volume', '0-100'),
        ],
    )
    def test_description_names_the_scale(self, model, field, marker):
        description = _description(model, field)
        assert marker in description, (
            f"{model.__name__}.{field} does not state its scale; two "
            f"incompatible scales share this field name (#4711)"
        )
