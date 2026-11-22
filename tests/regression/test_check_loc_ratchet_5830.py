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


@pytest.mark.parametrize(
    "name, expected",
    [
        ("auralis/core/engine.py", True),
        ("auralis-web/backend/core/job_worker.py", True),
        ("auralis-web/frontend/src/components/Player.tsx", True),
        ("auralis-web/frontend/src/test/mocks/handlers.ts", False),
        ("auralis-web/frontend/src/components/__tests__/Player.test.tsx", False),
        ("scripts/check_loc_ratchet.py", False),
        ("tests/backend/test_big.py", False),
        ("vendor/auralis-dsp/src/rhythm.rs", False),
    ],
)
def test_product_scope_is_shipped_code_only(name, expected):
    """#6701: the unlisted-file rule covers shipped code, not tests, scripts or the Rust crate."""
    assert gate.is_product_file(name) is expected


def test_unlisted_product_file_over_the_limit_is_reported(tmp_path):
    """#6701: a closed split target nobody enrolled must not regrow past 300 silently."""
    for name, count in {
        "auralis/big.py": 301,
        "auralis/at_limit.py": 300,
        "auralis/listed_big.py": 320,
        "scripts/tool.py": 900,
    }.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        _write_lines(tmp_path / name, count)

    offenders = gate.unlisted_offenders(
        {"auralis/listed_big.py": 320},
        ["auralis/big.py", "auralis/at_limit.py", "auralis/listed_big.py", "scripts/tool.py"],
        root=tmp_path,
    )

    assert offenders == {"auralis/big.py": 301}


def test_real_tree_has_no_unlisted_product_file_over_300():
    assert gate.unlisted_offenders(gate.load_ceilings(), gate.tracked_files()) == {}
