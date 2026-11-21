"""
Large-library perf/load/stress tests run nightly, not per push (#6708)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

tests/performance, tests/load_stress and tests/stress took ~1370 s of a ~2020 s
Backend Tests run and pushed the job to its 45-minute cap. The root conftest
marks every test under them ``slow``, so backend-tests.yml's ``-m "not slow"``
drops them and slow-tests.yml's ``-m slow`` picks them up.

These tests collect in a subprocess, so they check what pytest actually
selects, not just that the hook exists.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import NIGHTLY_ONLY_DIRS

REPO_ROOT = Path(__file__).parent.parent


def _collected(marker_expr: str, *paths: str) -> list[str]:
    # Two -q: pytest.ini's addopts carries --verbose, and one -q only cancels it
    # back to the tree view, which prints no node ids.
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-q", "-p", "no:randomly",
         "-m", marker_expr, *paths],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode in (0, 5), result.stdout[-2000:] + result.stderr[-2000:]
    return [line for line in result.stdout.splitlines() if "::" in line]


@pytest.mark.parametrize("directory", sorted(NIGHTLY_ONLY_DIRS))
def test_directory_is_deselected_per_push_and_selected_nightly(directory: str):
    path = f"tests/{directory}"
    assert (REPO_ROOT / path).is_dir(), f"{path} is gone; drop it from NIGHTLY_ONLY_DIRS"

    nightly = _collected("slow", path)
    assert nightly, f"-m slow collected nothing under {path}"
    assert _collected("not slow", path) == [], f"{path} still runs in the per-push job"


def test_other_directories_are_not_swept_into_the_nightly_job():
    """The rule is by top-level directory, not a substring match on the path."""
    per_push = _collected("not slow", "tests/test_conftest_hooks_4529.py")
    assert per_push, "an unrelated file was marked slow"
