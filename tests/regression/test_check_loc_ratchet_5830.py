"""
LOC ratchet for closed split targets (#5830)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``enhanced_audio_player.py`` was closed at 296 lines and regrew to 314;
``chunked_processor.py`` sat at exactly 300; ``hybrid_processor.py`` passed the
waiver ceiling its own docstring states. ``scripts/check_loc_ratchet.py`` holds
each listed file to a ceiling in ``loc-ceilings.json``.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_loc_ratchet.py"
_spec = importlib.util.spec_from_file_location("check_loc_ratchet", _SCRIPT)
gate = importlib.util.module_from_spec(_spec)
sys.modules["check_loc_ratchet"] = gate
_spec.loader.exec_module(gate)

pytestmark = pytest.mark.regression


def _write_lines(path: Path, count: int) -> None:
    path.write_text("x = 1\n" * count)


def test_count_lines_matches_wc(tmp_path):
    target = tmp_path / "a.py"
    _write_lines(target, 7)

    assert gate.count_lines(target) == 7


def test_measure_reports_missing_files_as_none(tmp_path):
    _write_lines(tmp_path / "here.py", 3)

    sizes = gate.measure({"here.py": 10, "gone.py": 10}, root=tmp_path)

    assert sizes == {"here.py": 3, "gone.py": None}


def test_ceilings_round_trip_sorted(tmp_path):
    path = tmp_path / "ceilings.json"

    gate.write_ceilings({"b.py": 2, "a.py": 1}, path)

    assert list(json.loads(path.read_text())["ceilings"]) == ["a.py", "b.py"]
    assert gate.load_ceilings(path) == {"a.py": 1, "b.py": 2}


def test_shipped_ceilings_hold_on_the_real_tree():
    ceilings = gate.load_ceilings()
    sizes = gate.measure(ceilings)

    assert not [n for n, s in sizes.items() if s is None], "a listed split target no longer exists"
    assert {n: (s, ceilings[n]) for n, s in sizes.items() if s > ceilings[n]} == {}


def test_player_and_chunked_processor_stay_under_300():
    """The CLAUDE.md '< 300' rule for the two split targets that had crossed it."""
    sizes = gate.measure(gate.load_ceilings())

    assert sizes["auralis/player/enhanced_audio_player.py"] < 300
    assert sizes["auralis-web/backend/core/chunked_processor.py"] < 300
