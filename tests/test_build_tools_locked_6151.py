"""
Release build tooling is hash-locked (#6151)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``build-release.yml`` hash-locked the runtime dependencies (#4871) but ran
``pip install --upgrade pip setuptools wheel maturin`` and ``pip install
pyinstaller`` unpinned on all three platforms. The authoritative check is
``.github/scripts/check_build_tools_locked.py`` (a ``requirements-pin-guard.yml``
job); these tests run it locally and pin what it must catch.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "check_build_tools_locked.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-release.yml"
PIN_GUARD = REPO_ROOT / ".github" / "workflows" / "requirements-pin-guard.yml"


@pytest.fixture(scope="module")
def guard():
    spec = importlib.util.spec_from_file_location("check_build_tools_locked", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_guard_passes_on_the_repository():
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=REPO_ROOT)

    assert result.returncode == 0, result.stdout + result.stderr


def test_every_build_tool_is_pinned_and_hashed(guard):
    pins, hashed = guard.lock_entries(REPO_ROOT / "requirements-build.txt")

    for tool in ("pip", "setuptools", "wheel", "maturin", "pyinstaller"):
        assert tool in pins and tool in hashed, tool
    assert set(pins) == hashed


def test_release_workflow_has_no_unlocked_pip_install(guard):
    assert guard.unlocked_pip_installs(WORKFLOW) == []


def test_each_build_job_installs_the_build_lock_before_the_runtime_lock():
    text = WORKFLOW.read_text()

    assert text.count("pip install --require-hashes -r requirements-build.txt") == 3
    for job_start in [m for m in range(len(text)) if text.startswith("-r requirements-build.txt", m)]:
        assert text.index("-r requirements-lock.txt", job_start) > job_start


@pytest.mark.parametrize(
    "line",
    [
        "pip install --upgrade pip setuptools wheel maturin",
        "pip install pyinstaller",
        "pip install --require-hashes --upgrade pip",
        "pip install target/wheels/*.whl",
    ],
)
def test_guard_flags_floating_installs(guard, tmp_path, line):
    workflow = tmp_path / "wf.yml"
    workflow.write_text(f"jobs:\n  build:\n    steps:\n      - run: |\n          {line}\n")

    assert len(guard.unlocked_pip_installs(workflow)) == 1


def test_guard_accepts_hash_checked_and_local_wheel_installs(guard, tmp_path):
    workflow = tmp_path / "wf.yml"
    workflow.write_text(
        "          pip install --require-hashes -r requirements-build.txt\n"
        "          pip install --no-deps target/wheels/*.whl\n"
        "          # pip install pyinstaller (a comment)\n"
    )

    assert guard.unlocked_pip_installs(workflow) == []


def test_guard_flags_a_lock_entry_without_hashes(guard, tmp_path):
    lock = tmp_path / "requirements-build.txt"
    lock.write_text("pyinstaller==6.22.3 \\\n    --hash=sha256:abc\npefile==2024.8.26\n")

    pins, hashed = guard.lock_entries(lock)

    assert set(pins) - hashed == {"pefile"}


def test_pin_guard_workflow_runs_the_script():
    text = PIN_GUARD.read_text()

    assert "check_build_tools_locked.py" in text
