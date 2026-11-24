"""
Lenient rejection tests in the weak-assertion gate (#6499)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``test_reorder_invalid_indices`` asserted ``status_code in [200, 400, 422]``. That passed whether
the endpoint rejected the indices or accepted them, and it hid that the request body was the wrong
schema. A test named for a rejection whose status set admits a 2xx is now reported with the other
assertions that cannot fail. Data-dependent sets in ordinary tests (``[200, 404]``) are left alone.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_weak_assertions.py"
_spec = importlib.util.spec_from_file_location("check_weak_assertions_6499", _SCRIPT)
gate = importlib.util.module_from_spec(_spec)
sys.modules["check_weak_assertions_6499"] = gate
_spec.loader.exec_module(gate)

pytestmark = pytest.mark.regression


def _scan(tmp_path, source):
    path = tmp_path / "test_sample.py"
    path.write_text(source)
    return sorted(name.split("::")[1] for name in gate.scan_file(path))


@pytest.mark.parametrize("name", [
    "test_reorder_invalid_indices", "test_seek_negative_position", "test_pagination_overflow_protection",
    "test_remove_from_queue_accepts_delete_only",
])
def test_a_rejection_test_that_admits_success_is_reported(tmp_path, name):
    assert _scan(tmp_path, (
        f"def {name}(client):\n"
        "    response = client.put('/x', json={})\n"
        "    assert response.status_code in [200, 400, 422]\n"
    )) == [name]


@pytest.mark.parametrize("source", [
    # a rejection test that only admits error codes
    "def test_seek_negative_position(client):\n    assert client.post('/x').status_code in (400, 422)\n",
    # an exact rejection status
    "def test_seek_negative_position(client):\n    assert client.post('/x').status_code == 422\n",
    # a data-dependent set in a test not named for a rejection
    "def test_workflow_get_album_details(client):\n    assert client.get('/x').status_code in [200, 404]\n",
])
def test_honest_status_assertions_are_not_reported(tmp_path, source):
    assert _scan(tmp_path, source) == []
