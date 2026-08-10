"""Validate release metadata without importing the application.

This script intentionally uses only the Python standard library so the
GitHub Actions release preflight can run before project dependencies are
installed.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(alpha|beta|rc)\.(0|[1-9]\d*))?$"
)
PACKAGE_FILES = (
    Path("package.json"),
    Path("auralis-web/frontend/package.json"),
    Path("desktop/package.json"),
)


def _literal_assignments(relative_path: Path) -> dict[str, Any]:
    """Return top-level literal assignments from a Python source file."""
    source_path = PROJECT_ROOT / relative_path
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    assignments: dict[str, Any] = {}

    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            value_node = node.value
        else:
            if not isinstance(node.target, ast.Name) or node.value is None:
                continue
            name = node.target.id
            value_node = node.value

        try:
            assignments[name] = ast.literal_eval(value_node)
        except (ValueError, TypeError):
            continue

    return assignments


def _require_match(
    errors: list[str],
    relative_path: Path,
    pattern: str,
    expected: str,
    label: str,
    *,
    flags: int = 0,
) -> None:
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    match = re.search(pattern, source, flags)
    if match is None:
        errors.append(f"{relative_path}: could not find {label}")
    elif match.group(1) != expected:
        errors.append(
            f"{relative_path}: {label} is {match.group(1)!r}, expected {expected!r}"
        )


def validate_release_metadata(expected: str | None = None) -> list[str]:
    """Return validation errors; an empty list means the metadata is coherent."""
    errors: list[str] = []
    canonical = _literal_assignments(Path("auralis/version.py"))
    compatibility = _literal_assignments(Path("auralis/__version__.py"))

    version = canonical.get("__version__")
    if not isinstance(version, str):
        return ["auralis/version.py: __version__ is missing or is not a string"]

    match = SEMVER_PATTERN.fullmatch(version)
    if match is None:
        errors.append(
            "auralis/version.py: __version__ must be "
            "MAJOR.MINOR.PATCH[-alpha|beta|rc.NUMBER]"
        )
        return errors

    if expected is not None:
        if SEMVER_PATTERN.fullmatch(expected) is None:
            errors.append(
                f"requested release {expected!r} is not a supported Semantic Version"
            )
        elif expected != version:
            errors.append(
                f"requested release {expected!r} does not match canonical version {version!r}"
            )

    major, minor, patch, prerelease_type, prerelease_number = match.groups()
    core = (int(major), int(minor), int(patch))
    prerelease = (
        f"{prerelease_type}.{prerelease_number}" if prerelease_type else ""
    )
    version_info = (*core, prerelease_type or "", int(prerelease_number or 0))

    expected_assignments = {
        "__version__": version,
        "__version_info__": version_info,
        "VERSION_MAJOR": core[0],
        "VERSION_MINOR": core[1],
        "VERSION_PATCH": core[2],
        "VERSION_PRERELEASE": prerelease,
    }
    for name, expected_value in expected_assignments.items():
        actual = canonical.get(name)
        if actual != expected_value:
            errors.append(
                f"auralis/version.py: {name} is {actual!r}, expected {expected_value!r}"
            )

    for name in ("__version__", "__version_info__"):
        actual = compatibility.get(name)
        expected_value = expected_assignments[name]
        if actual != expected_value:
            errors.append(
                f"auralis/__version__.py: {name} is {actual!r}, "
                f"expected {expected_value!r}"
            )

    for relative_path in PACKAGE_FILES:
        package = json.loads(
            (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        )
        if package.get("version") != version:
            errors.append(
                f"{relative_path}: version is {package.get('version')!r}, "
                f"expected {version!r}"
            )

    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    pyproject_version = pyproject.get("project", {}).get("version")
    if pyproject_version != version:
        errors.append(
            f"pyproject.toml: project.version is {pyproject_version!r}, "
            f"expected {version!r}"
        )

    build_date = canonical.get("__build_date__")
    if not isinstance(build_date, str):
        errors.append("auralis/version.py: __build_date__ is missing or invalid")
        build_date = ""

    _require_match(
        errors,
        Path("auralis-web/backend/routers/health.py"),
        r'VersionInfoResponse\(\s*version="([^"]+)"',
        version,
        "degraded version fallback",
        flags=re.DOTALL,
    )
    _require_match(
        errors,
        Path("auralis-web/backend/routers/health.py"),
        r'VersionInfoResponse\(.*?build_date="([^"]+)"',
        build_date,
        "degraded build-date fallback",
        flags=re.DOTALL,
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected",
        help="Version requested by a release tag or manual workflow dispatch",
    )
    args = parser.parse_args()

    errors = validate_release_metadata(args.expected)
    if errors:
        print("Release metadata validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    version = _literal_assignments(Path("auralis/version.py"))["__version__"]
    print(f"Release metadata is consistent for Auralis v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
