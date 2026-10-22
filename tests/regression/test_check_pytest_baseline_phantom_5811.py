"""
Phantom baseline entries (#5811).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--strict-stale`` (#5091) catches a baselined test that RAN and PASSED. A
baselined test that no longer exists is never in a report, so it is "not run"
and invisible to that check: two such entries (a renamed method and a deleted
module) sat in ``pytest-baseline.json``, re-permitting any future test that
reuses the name. ``phantom_entries`` finds them statically, from the node id
alone, so it works on a scoped run too.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "check_pytest_baseline.py"
_spec = importlib.util.spec_from_file_location("check_pytest_baseline_phantom", _SCRIPT_PATH)
gate = importlib.util.module_from_spec(_spec)
sys.modules["check_pytest_baseline_phantom"] = gate
_spec.loader.exec_module(gate)

_REAL_REPO_ROOT = gate.REPO_ROOT


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A repo whose tests/ has one module with one class and two tests."""
    (tmp_path / "tests" / "pkg").mkdir(parents=True)
    (tmp_path / "tests" / "pkg" / "test_real.py").write_text(
        "class TestThing:\n"
        "    def test_present(self): ...\n"
        "def test_module_level(): ...\n"
    )
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    return tmp_path


@pytest.mark.regression
class TestPhantomEntries:
    def test_existing_class_method_and_module_function_are_not_phantoms(self, fake_repo):
        entries = {
            "tests.pkg.test_real.TestThing::test_present",
            "tests.pkg.test_real::test_module_level",
        }
        assert gate.phantom_entries(entries) == []

    def test_a_deleted_module_is_a_phantom(self, fake_repo):
        entry = "tests.pkg.test_gone.TestThing::test_present"
        assert gate.phantom_entries({entry}) == [entry]

    def test_a_renamed_test_is_a_phantom(self, fake_repo):
        entry = "tests.pkg.test_real.TestThing::test_old_name"
        assert gate.phantom_entries({entry}) == [entry]

    def test_a_removed_class_is_a_phantom(self, fake_repo):
        entry = "tests.pkg.test_real.TestGone::test_present"
        assert gate.phantom_entries({entry}) == [entry]

    def test_a_parametrize_suffix_is_ignored(self, fake_repo):
        assert gate.phantom_entries({"tests.pkg.test_real::test_module_level[a-1]"}) == []

    def test_only_the_phantoms_are_returned(self, fake_repo):
        good = "tests.pkg.test_real::test_module_level"
        bad = "tests.pkg.test_real::test_nope"
        assert gate.phantom_entries({good, bad}) == [bad]


@pytest.mark.regression
def test_shipped_baseline_has_no_phantom_entries(monkeypatch):
    """The real pytest-baseline.json, against the real tree."""
    monkeypatch.setattr(gate, "REPO_ROOT", _REAL_REPO_ROOT)
    assert gate.phantom_entries(gate.load_baseline()) == []
