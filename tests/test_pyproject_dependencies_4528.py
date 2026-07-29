"""
pyproject.toml runtime dependency set (issue #4528)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`[project.dependencies]` had drifted off the real dependency set far enough that
`pip install -e .` produced an environment which could not import
`auralis.library` — SQLAlchemy was simply absent, along with 8 other runtime
dependencies — while declaring four packages with zero importers repo-wide.

The authoritative check is `.github/scripts/check_pyproject_deps.py`, wired into
`requirements-pin-guard.yml`. These tests run that same script locally so the
drift is caught before CI, and pin the specific facts the issue turned on.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
GUARD = REPO_ROOT / ".github" / "scripts" / "check_pyproject_deps.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "requirements-pin-guard.yml"


def _runtime_specs() -> list[str]:
    return tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]


def _dev_specs() -> list[str]:
    data = tomllib.loads(PYPROJECT.read_text())
    return data["project"]["optional-dependencies"]["dev"]


def _names(specs: list[str]) -> set[str]:
    out = set()
    for spec in specs:
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", spec.strip())
        if m:
            out.add(re.sub(r"[-_.]+", "-", m.group(1)).lower())
    return out


def test_guard_script_passes():
    """The CI guard must be green against the committed manifests."""
    result = subprocess.run(
        [sys.executable, str(GUARD)], capture_output=True, text=True, cwd=REPO_ROOT
    )
    assert result.returncode == 0, (
        f"check_pyproject_deps.py failed:\n{result.stdout}\n{result.stderr}"
    )


def test_guard_is_wired_into_a_pull_request_workflow():
    """A guard nobody runs is not a guard (WIRING).

    Asserts the script is invoked from the workflow AND that the workflow
    triggers on pull_request — an unreferenced script would pass a naive
    'file exists' check.
    """
    assert GUARD.exists()
    workflow = WORKFLOW.read_text()
    assert "check_pyproject_deps.py" in workflow, (
        "the guard script is not referenced by requirements-pin-guard.yml"
    )
    assert re.search(r"^on:", workflow, re.MULTILINE)
    assert re.search(r"^\s+pull_request:", workflow, re.MULTILINE), (
        "requirements-pin-guard.yml does not trigger on pull_request"
    )


@pytest.mark.parametrize(
    "package",
    ["sqlalchemy", "mutagen", "pillow", "aiohttp", "psutil", "resampy",
     "python-multipart"],
)
def test_core_runtime_dependency_is_declared(package: str):
    """Each of these is imported (or required) by production code."""
    assert package in _names(_runtime_specs())


@pytest.mark.parametrize("package", ["pyqt6", "audioread", "sounddevice", "websockets"])
def test_unimported_package_is_not_a_runtime_dependency(package: str):
    """None of these has an importer in auralis/ or auralis-web/.

    PyQt6 alone pulled ~100 MB for nothing; sounddevice and websockets are
    test-only and now live in the `dev` extra instead.
    """
    assert package not in _names(_runtime_specs())


def test_no_pre_numpy2_floors():
    """Too-low floors are the inverse of a stale pin, and just as harmful.

    A resolver could legally have picked NumPy 1.x — where the removed
    `np.float`/`np.bool` aliases still exist and dtype promotion differs from
    the NumPy 2.x this DSP code targets — or a pre-0.100 FastAPI with neither
    Pydantic V2 support nor `lifespan`.
    """
    floors = {
        "numpy": (2, 0),
        "scipy": (1, 16),
        "fastapi": (0, 115),
        "pydantic": (2, 12),
        "sqlalchemy": (2, 0),
    }
    seen: dict[str, tuple[int, ...]] = {}
    for spec in _runtime_specs():
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)[^>]*>=\s*([0-9][0-9.]*)", spec)
        if m:
            name = re.sub(r"[-_.]+", "-", m.group(1)).lower()
            seen[name] = tuple(int(p) for p in m.group(2).split("."))

    for name, minimum in floors.items():
        assert name in seen, f"{name} has no >= floor in [project.dependencies]"
        actual = seen[name]
        padded = actual + (0,) * (len(minimum) - len(actual))
        assert padded >= minimum, (
            f"{name} floor {actual} is below the verified minimum {minimum}"
        )


def test_numpy_is_capped_below_numba_ceiling():
    """librosa/resampy pull numba, and numba 0.66 requires `numpy<2.5`.

    Without this cap the resolver takes numpy 2.5.1, backtracks numba to
    0.53.1 (a 2021 release with no numpy cap and no cp314 wheel) and the
    install dies building llvmlite 0.36 from source. `numpy>=2.0` alone — the
    fix as originally proposed — still produces a broken environment.
    """
    numpy_spec = next(s for s in _runtime_specs() if s.lower().startswith("numpy"))
    assert "<2.5" in numpy_spec.replace(" ", ""), (
        f"numpy spec {numpy_spec!r} has no upper bound; the resolver will pick "
        "a numpy newer than numba supports"
    )


def test_test_only_packages_live_in_the_dev_extra():
    dev = _names(_dev_specs())
    for package in ("sounddevice", "websockets", "httpx", "pytest"):
        assert package in dev
