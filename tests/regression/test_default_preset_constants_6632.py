"""
The default preset is named once per layer, and the layers agree (#6632)

schemas.DEFAULT_PRESET is the web-side definition (#5794). The engine may not import the web
schemas, so it names its own DEFAULT_PRESET_NAME; the frontend names DEFAULT_ENHANCEMENT_PRESET; and
the ORM column default stays a literal because the library may not import either. These tests are
what keeps the four equal, so the next preset change cannot miss a spelling.
"""

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from schemas import DEFAULT_PRESET, VALID_PRESETS  # noqa: E402

from auralis.core.config.preset_profiles import DEFAULT_PRESET_NAME, create_preset_profiles  # noqa: E402
from auralis.library.models.settings import UserSettings  # noqa: E402


def test_engine_default_matches_the_web_default():
    assert DEFAULT_PRESET_NAME == DEFAULT_PRESET
    assert DEFAULT_PRESET_NAME in VALID_PRESETS
    assert DEFAULT_PRESET_NAME in create_preset_profiles()


def test_settings_column_default_matches_the_web_default():
    assert UserSettings.__table__.c.default_preset.default.arg == DEFAULT_PRESET


def test_frontend_default_is_the_first_listed_preset_and_matches_the_backend():
    domain = (_ROOT / "auralis-web/frontend/src/types/domain.ts").read_text()
    listed = re.search(r"ENHANCEMENT_PRESETS: EnhancementPreset\[\] = \[\s*'(\w+)'", domain)

    assert "DEFAULT_ENHANCEMENT_PRESET: EnhancementPreset = ENHANCEMENT_PRESETS[0]" in domain
    assert listed and listed.group(1) == DEFAULT_PRESET


def test_no_runtime_site_spells_the_default_preset_as_a_literal():
    sites = [
        "auralis/core/config/unified_config.py",
        "auralis/core/processing/adaptive_mode.py",
        "auralis/core/analysis/spectrum_mapper/spectrum_mapper.py",
        "auralis/core/analysis/spectrum_mapper/content_modifiers.py",
        "auralis-web/backend/core/processor_factory.py",
        "auralis-web/backend/core/chunked_processor.py",
        "auralis-web/frontend/src/store/slices/playerSlice.ts",
        "auralis-web/frontend/src/hooks/enhancement/enhancementState.ts",
        "auralis-web/frontend/src/hooks/enhancement/usePlayEnhanced.ts",
        "auralis-web/frontend/src/components/settings/SettingsDialogContent.tsx",
    ]
    # Preset positions only: "adaptive" is also a processing *mode* (unified_config, job models).
    pattern = re.compile(
        r"""(?:preset\w*|mastering_profile)\s*(?::\s*[\w |]+)?=\s*['"]adaptive['"]"""
        r"""|(?:\?\?|else)\s*['"]adaptive['"]|startPlayback\([^)]*['"]adaptive['"]"""
    )
    offenders = []
    for rel in sites:
        code = [
            line for line in (_ROOT / rel).read_text().splitlines()
            if not line.lstrip().startswith(("#", "*", "//", '"', "'"))
        ]
        offenders += [f"{rel}: {line.strip()}" for line in code if pattern.search(line)]
    assert not offenders, "\n".join(offenders)
