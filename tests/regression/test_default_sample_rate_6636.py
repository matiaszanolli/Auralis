"""
The assumed sample rate has one home, and its mirrors agree (#6636)

44100 was retyped as a default in about twenty constructors and configs, two backend fallbacks
and four ad-hoc constants (#4622 and #4924 swept the same hazard before, and the count crept back).
DEFAULT_SAMPLE_RATE in auralis/dsp/constants.py is the one definition now; the ORM column default
and the frontend constant are mirrors these tests hold equal, and a scan keeps new literal
defaults out.
"""

import inspect
import re
from pathlib import Path

from auralis.dsp.constants import DEFAULT_SAMPLE_RATE
from auralis.library.models.settings import UserSettings

_ROOT = Path(__file__).resolve().parents[2]


def test_settings_column_default_mirrors_the_constant():
    assert UserSettings.__table__.c.sample_rate.default.arg == DEFAULT_SAMPLE_RATE


def test_frontend_stream_default_mirrors_the_constant():
    source = (_ROOT / "auralis-web/frontend/src/services/audio/audioConstants.ts").read_text()
    match = re.search(r"DEFAULT_STREAM_SAMPLE_RATE\s*=\s*(\d+)", source)

    assert match and int(match.group(1)) == DEFAULT_SAMPLE_RATE


def test_unified_config_defaults_to_the_constant():
    from auralis.core.config.unified_config import UnifiedConfig

    default = inspect.signature(UnifiedConfig.__init__).parameters["internal_sample_rate"].default
    assert default == DEFAULT_SAMPLE_RATE


def test_no_new_literal_sample_rate_default():
    """`sample_rate=44100`-style defaults and `or 44100` fallbacks are spelled with the constant."""
    pattern = re.compile(r"(?:\b(?:sample_rate|sr|internal_sample_rate)\s*(?::\s*int)?\s*=|\bor)\s*44100\b")
    offenders = []
    for tree in ("auralis", "auralis-web/backend"):
        for path in (_ROOT / tree).rglob("*.py"):
            for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                stripped = line.lstrip()
                if stripped.startswith(("#", ">>>", "...")) or "mapped_column" in line:
                    continue
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(_ROOT)}:{number}: {stripped}")
    assert not offenders, "\n".join(offenders)
