"""Tests for the shared scan/enhancement helpers (#4409, #4411).

- scan_progress_percentage: indeterminate (None) unless a real progress
  fraction is supplied, because the streaming scanner's processed/total is
  always ~100%.
- seed_enhancement_settings: maps persisted user settings into the runtime
  enhancement dict (in place).
- UserSettings.auto_enhance now defaults True so a fresh install keeps
  enhanced playback on.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from helpers import scan_progress_percentage, seed_enhancement_settings  # noqa: E402


class TestScanProgressPercentage:
    def test_indeterminate_without_progress_fraction(self):
        # Streaming scan: processed == total_found at every checkpoint.
        assert scan_progress_percentage({"processed": 500, "total_found": 500}) is None

    def test_indeterminate_on_empty(self):
        assert scan_progress_percentage({}) is None

    def test_uses_real_fraction_when_present(self):
        assert scan_progress_percentage({"progress": 0.42}) == 42
        assert scan_progress_percentage({"progress": 1.0}) == 100


class TestSeedEnhancementSettings:
    def _base(self):
        return {"preset": "adaptive", "intensity": 1.0, "enabled": True}

    def test_maps_all_three_fields(self):
        enh = self._base()
        seed_enhancement_settings(
            enh,
            SimpleNamespace(default_preset="warm", enhancement_intensity=0.6, auto_enhance=True),
        )
        assert enh == {"preset": "warm", "intensity": 0.6, "enabled": True}

    def test_auto_enhance_false_disables(self):
        enh = self._base()
        seed_enhancement_settings(
            enh,
            SimpleNamespace(default_preset="gentle", enhancement_intensity=0.3, auto_enhance=False),
        )
        assert enh["enabled"] is False

    def test_none_settings_is_noop(self):
        enh = self._base()
        seed_enhancement_settings(enh, None)
        assert enh == {"preset": "adaptive", "intensity": 1.0, "enabled": True}

    def test_mutates_in_place(self):
        enh = self._base()
        result = seed_enhancement_settings(
            enh, SimpleNamespace(default_preset="bright", enhancement_intensity=0.9, auto_enhance=True)
        )
        assert result is None  # in-place, no return
        assert enh["preset"] == "bright"


def test_user_settings_auto_enhance_defaults_true():
    """#4409: fresh settings must keep enhanced playback enabled.

    The default is a SQLAlchemy column default applied on INSERT, so assert on
    the column definition (a bare instance has None until flushed).
    """
    from auralis.library.models.settings import UserSettings

    assert UserSettings.__table__.c.auto_enhance.default.arg is True
