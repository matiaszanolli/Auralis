"""
Regression test for scripts/check_breadcrumbs.py (#6257)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

'was removed/deleted in #NNNN' breadcrumb comments regrew six times after
manual sweeps (#4088, #4293, #4649, #5034, #5820, 2026-10-22 audit) because
nothing gated them. This pins the gate itself: a breadcrumb fails the check,
a present-tense constraint passes, and a behavioral docstring ("True if
track was removed") does not trip it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_breadcrumbs.py"


def _run_with_file(tmp_path: Path, body: str) -> int:
    """Run the gate against a scratch tree containing one file."""
    (tmp_path / "auralis").mkdir(exist_ok=True)
    (tmp_path / "auralis" / "scratch.py").write_text(body)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    ).returncode


def test_breadcrumb_comment_fails_the_gate(tmp_path: Path) -> None:
    assert (
        _run_with_file(tmp_path, "# helper was deleted in #1234\nX = 1\n") == 1
    )


def test_breadcrumb_variants_fail_the_gate(tmp_path: Path) -> None:
    for body in (
        "# flags were removed by #42\n",
        "# layer has been dropped with #7\n",
        "// widget was retired in #9\n",
    ):
        assert _run_with_file(tmp_path, body) == 1, body


def test_present_tense_constraint_passes(tmp_path: Path) -> None:
    assert (
        _run_with_file(
            tmp_path,
            "# Do not re-add the helper: it raced process_chunk (#1234).\nX = 1\n",
        )
        == 0
    )


def test_behavioral_docstring_passes(tmp_path: Path) -> None:
    """Docstrings like 'True if track was removed' have no issue ref — keep."""
    assert (
        _run_with_file(
            tmp_path,
            'def remove():\n    """True if track was removed, False otherwise."""\n',
        )
        == 0
    )
