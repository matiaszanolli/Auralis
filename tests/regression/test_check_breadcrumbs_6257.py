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


def test_file_line_anchor_fails_the_gate(tmp_path: Path) -> None:
    """#6675: `file.py:597`-style anchors rot when the cited file changes."""
    for body in (
        "# Mirrors the streaming path at audio_stream_controller.py:597.\n",
        "# matches the contract (types/ws/enhancement.ts:71-78, #4676)\n",
        "// see useAudioStreamingCore.tsx:460\n",
    ):
        assert _run_with_file(tmp_path, body) == 1, body


def test_symbol_anchor_and_ratio_pass(tmp_path: Path) -> None:
    """Symbol citations and non-file `x:N` text are not line anchors."""
    body = (
        "# Mirrors stream_enhanced_lifecycle.run_enhanced_stream (#6675).\n"
        "RATIO = '4:1'  # compression ratio, not a file reference\n"
    )
    assert _run_with_file(tmp_path, body) == 0


def test_wider_narration_forms_fail_the_gate(tmp_path: Path) -> None:
    """#6680: past-tense narrations beyond 'was removed in #N'."""
    for body in (
        "# the reset path went with #4873\n",
        "// the unused helper went in #5738\n",
        "# the duplicates were removed (#3824)\n",
        "# The standardized client is retired (#4693): its types survive\n",
        "# mirrored the now-deleted AdaptiveLimiter — #4873\n",
        "# that executor is gone, see #4744\n",
        "# Removed following #5309's precedent\n",
    ):
        assert _run_with_file(tmp_path, body) == 1, body


def test_line_wrapped_breadcrumb_fails_the_gate(tmp_path: Path) -> None:
    """#6680: 'was' / 'removed in #N' split across two comment lines."""
    body = "# a third axis was\n# removed in #6123: no parameter read it\nX = 1\n"
    assert _run_with_file(tmp_path, body) == 1


def test_runtime_gone_and_test_docstrings_pass(tmp_path: Path) -> None:
    """'is gone (#N)' describes runtime state; tests may name a removal."""
    assert _run_with_file(tmp_path, "# so the entry is gone (#5082)\n") == 0
    tests_dir = tmp_path / "auralis" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_guard.py").write_text('"""The helper went in #5738."""\n')
    assert _run_with_file(tmp_path, "X = 1\n") == 0
