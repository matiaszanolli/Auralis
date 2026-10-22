"""
Zero-assertion mode of the weak-assertion gate (#5807)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Roughly twenty collected tests ended in a comment ("this test documents expected
behavior") instead of an assertion and were green against any defect. ``--zero``
reports a ``test_*`` function that contains no assertion of any kind, while
leaving alone the shapes that do assert or are not tests.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_weak_assertions.py"
_spec = importlib.util.spec_from_file_location("check_weak_assertions_zero", _SCRIPT)
gate = importlib.util.module_from_spec(_spec)
sys.modules["check_weak_assertions_zero"] = gate
_spec.loader.exec_module(gate)

pytestmark = pytest.mark.regression


def _scan(tmp_path, source):
    path = tmp_path / "test_sample.py"
    path.write_text(source)
    return sorted(name.split("::")[1] for name in gate.scan_file_zero(path))


def test_a_test_that_ends_in_a_comment_is_reported(tmp_path):
    assert _scan(tmp_path, (
        "def test_documents_behaviour():\n"
        "    x = 1\n"
        "    # This test documents expected behavior\n"
    )) == ["test_documents_behaviour"]


@pytest.mark.parametrize(
    "body",
    [
        "    assert 1 == 1\n",
        "    with pytest.raises(ValueError):\n        int('x')\n",
        "    with pytest.warns(UserWarning):\n        pass\n",
        "    mock.assert_called_once()\n",
        "    np.testing.assert_allclose(a, b)\n",
        "    self.assertEqual(a, b)\n",
        "    _check_invariants(result)\n",
        "    verify_roundtrip(result)\n",
        "    pytest.fail('nope')\n",
    ],
)
def test_anything_that_asserts_is_left_alone(tmp_path, body):
    assert _scan(tmp_path, f"def test_it():\n{body}") == []


def test_fixtures_and_skipped_tests_are_not_reported(tmp_path):
    assert _scan(tmp_path, (
        "import pytest\n"
        "@pytest.fixture\n"
        "def test_db():\n    return 1\n"
        "@pytest.mark.skip(reason='x')\n"
        "def test_skipped():\n    pass\n"
        "@pytest.mark.xfail\n"
        "def test_expected_failure():\n    pass\n"
    )) == []


def test_methods_are_reported_too(tmp_path):
    assert _scan(tmp_path, (
        "class TestThing:\n"
        "    def test_nothing(self):\n"
        "        pass\n"
    )) == ["test_nothing"]


def test_shipped_baseline_has_no_stale_entries():
    """Every baselined test still exists and still asserts nothing."""
    current = set(gate.find_offenders(scan=gate.scan_file_zero))
    baseline = gate.load_baseline(gate.ZERO_BASELINE_PATH)

    assert baseline - current == set(), "shrink it: scripts/check_weak_assertions.py --zero --update"
    assert current - baseline == set(), "a new zero-assertion test: assert something"
