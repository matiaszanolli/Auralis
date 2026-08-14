#!/usr/bin/env python3
"""Keep pyproject.toml's runtime dependency set in step with requirements.txt (#4528).

`pyproject.toml` had drifted so far off `requirements.txt` that
``pip install -e .`` produced an environment which could not import
``auralis.library`` at all — SQLAlchemy was absent, along with 8 other runtime
dependencies — while declaring four packages with zero importers repo-wide
(PyQt6 alone pulling ~100 MB).

Nothing compared the two files, so the drift was invisible. This check runs on
every PR (``requirements-pin-guard.yml``) and fails on any package present in
one and absent from the other, except for the explicitly-justified entries in
``NOT_DIRECT_DEPENDENCIES`` below.

Exit code 0 on success, 1 on drift.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
REQUIREMENTS = REPO_ROOT / "requirements.txt"

# Packages pinned in requirements.txt that are deliberately NOT declared as
# direct dependencies in pyproject.toml. Every entry needs a reason: an
# unexplained exception here is how the original drift stayed invisible.
NOT_DIRECT_DEPENDENCIES: dict[str, str] = {
    # Pinned transitively for reproducible installs, not imported by us.
    "h11": "transitive: required by httpcore and uvicorn",
    "httpcore": "transitive: required by httpx",
    # #4871: this read "required by pydantic-settings", which was wrong even
    # before that pin was dropped — the actual requirer is `uvicorn[standard]`
    # (`python-dotenv>=0.13; extra == "standard"`). A wrong reason here is not
    # cosmetic: it is what someone reads when deciding whether the entry can go.
    "python-dotenv": "transitive: required by uvicorn[standard]",
    # Test-only; declared in the `dev` extra instead.
    "httpx": "test-only: fastapi.testclient.TestClient",
}
# `pydantic-settings` used to be exempted here as "UNUSED: zero importers
# repo-wide - see #4355". #4871 removed the pin itself from both manifests
# instead: it is absent from pyproject.toml, absent from the installed .venv,
# and imported by nothing — so it was describing a package the app neither
# declares nor ships. `starlette` moved the opposite way in the same change:
# it is imported directly by five backend modules and is now a declared
# dependency rather than an undeclared transitive.


def normalize(name: str) -> str:
    """PEP 503 normalisation, so `SQLAlchemy` and `sqlalchemy` compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_names(path: Path) -> set[str]:
    names: set[str] = set()
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        # Strip extras and any version specifier: `uvicorn[standard]==0.38.0`.
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", line)
        if match:
            names.add(normalize(match.group(1)))
    return names


def pyproject_names(path: Path) -> set[str]:
    data = tomllib.loads(path.read_text())
    names: set[str] = set()
    for spec in data["project"].get("dependencies", []):
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", spec.strip())
        if match:
            names.add(normalize(match.group(1)))
    return names


def main() -> int:
    for path in (PYPROJECT, REQUIREMENTS):
        if not path.exists():
            print(f"::error::Missing manifest: {path}")
            return 1

    declared = pyproject_names(PYPROJECT)
    pinned = requirement_names(REQUIREMENTS)
    exempt = {normalize(name) for name in NOT_DIRECT_DEPENDENCIES}

    missing = sorted(pinned - declared - exempt)
    extra = sorted(declared - pinned)

    status = 0

    if missing:
        status = 1
        print(
            "::error file=pyproject.toml::Pinned in requirements.txt but not "
            "declared in [project.dependencies] (#4528)"
        )
        for name in missing:
            print(f"  - {name}")
        print(
            "\n`pip install -e .` will not install these, so a metadata-driven\n"
            "install yields a different environment from requirements.txt.\n"
            "Add each one with a floor at its pinned major/minor, or add it to\n"
            "NOT_DIRECT_DEPENDENCIES in this script WITH A REASON."
        )

    if extra:
        status = 1
        print(
            "::error file=pyproject.toml::Declared in [project.dependencies] "
            "but not pinned in requirements.txt (#4528)"
        )
        for name in extra:
            print(f"  - {name}")
        print(
            "\nThese resolve to whatever PyPI offers at install time, against a\n"
            "version nobody has tested. Pin them in requirements.txt, or drop\n"
            "them if they have no importer (this is how PyQt6 survived here)."
        )

    if status == 0:
        print(
            f"OK: pyproject.toml declares {len(declared)} runtime dependencies, "
            f"consistent with requirements.txt "
            f"({len(exempt)} documented exceptions)."
        )

    return status


if __name__ == "__main__":
    sys.exit(main())
