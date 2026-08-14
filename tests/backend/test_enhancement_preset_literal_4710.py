"""
Enhancement response models use the shared preset Literal (#4710)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#4424 made `EnhancementPresetLiteral` the single source of truth and migrated
the *request* side; `EnhancementSettings.preset` and
`PlayerState.current_preset` stayed bare `str` until #4710. The frontend
narrows on the same closed union, so a non-canonical preset serialized
straight through and dropped the enhancement UI out of its switch — and
OpenAPI advertised a free-form string for a closed enum.

Tightening the response model turns a silently-wrong value into a loud
failure, which is only an improvement if a *legitimate* stored value cannot
trigger it. `UserSettings.default_preset` is a plain String column, so #4710
also guarded `seed_enhancement_settings` — those tests are here too.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

_backend_dir = Path(__file__).parent.parent.parent / 'auralis-web' / 'backend'
sys.path.insert(0, str(_backend_dir))

if 'routers' not in sys.modules:
    _stub = types.ModuleType('routers')
    _stub.__path__ = [str(_backend_dir / 'routers')]
    _stub.__package__ = 'routers'
    sys.modules['routers'] = _stub

from helpers import seed_enhancement_settings  # noqa: E402
from player_state import PlayerState  # noqa: E402
from routers.enhancement import EnhancementSettings  # noqa: E402
from schemas import VALID_PRESETS  # noqa: E402


class TestEnhancementSettingsPreset:
    @pytest.mark.parametrize("preset", VALID_PRESETS)
    def test_accepts_every_canonical_preset(self, preset):
        model = EnhancementSettings(enabled=True, preset=preset, intensity=0.5)
        assert model.preset == preset

    @pytest.mark.parametrize("preset", ["Warm", "ADAPTIVE", "nonsense", "", "profile:rock"])
    def test_rejects_non_canonical_presets(self, preset):
        """Including capitalisations — the request side lowercases, this does not."""
        with pytest.raises(Exception):
            EnhancementSettings(enabled=True, preset=preset, intensity=0.5)

    @pytest.mark.parametrize("intensity", [-0.1, 1.1, float('nan'), float('inf')])
    def test_rejects_out_of_range_intensity(self, intensity):
        """EnhancementIntensity's ge/le also reject NaN and inf (#4600)."""
        with pytest.raises(Exception):
            EnhancementSettings(enabled=True, preset='adaptive', intensity=intensity)

    def test_accepts_range_endpoints(self):
        for intensity in (0.0, 1.0):
            assert EnhancementSettings(
                enabled=True, preset='adaptive', intensity=intensity
            ).intensity == intensity


class TestPlayerStateLiterals:
    def test_defaults_are_canonical(self):
        state = PlayerState()
        assert state.repeat_mode == 'off'
        assert state.current_preset == 'adaptive'

    @pytest.mark.parametrize("mode", ['off', 'one', 'all'])
    def test_accepts_every_repeat_mode(self, mode):
        assert PlayerState(repeat_mode=mode).repeat_mode == mode

    def test_rejects_the_legacy_none_repeat_mode(self):
        """Pre-#3501 code stored 'none' here, which the frontend never matched."""
        with pytest.raises(Exception):
            PlayerState(repeat_mode='none')


class TestSeedEnhancementSettingsGuard:
    """A stored preset outside the closed set must not 500 the status endpoint."""

    def test_seeds_a_valid_stored_preset(self):
        settings = {'preset': 'adaptive', 'intensity': 1.0, 'enabled': True}
        seed_enhancement_settings(
            settings,
            SimpleNamespace(default_preset='warm', enhancement_intensity=0.4, auto_enhance=True),
        )
        assert settings['preset'] == 'warm'
        assert settings['intensity'] == 0.4

    def test_ignores_an_off_list_stored_preset(self):
        """The whole point: the seeded dict must stay inside the Literal."""
        settings = {'preset': 'adaptive', 'intensity': 1.0, 'enabled': True}
        seed_enhancement_settings(
            settings,
            SimpleNamespace(default_preset='legacy-mode', enhancement_intensity=0.4, auto_enhance=True),
        )
        assert settings['preset'] == 'adaptive'
        # And the result is still constructible as a response model.
        EnhancementSettings(
            enabled=settings['enabled'],
            preset=settings['preset'],
            intensity=settings['intensity'],
        )

    def test_none_user_settings_is_a_noop(self):
        settings = {'preset': 'gentle', 'intensity': 0.3, 'enabled': False}
        seed_enhancement_settings(settings, None)
        assert settings == {'preset': 'gentle', 'intensity': 0.3, 'enabled': False}
