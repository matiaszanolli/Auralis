"""Release metadata must agree with the canonical product version."""

from __future__ import annotations

import importlib
import json
import re
import tomllib
from pathlib import Path

from auralis import version as product_version
from scripts.validate_release_metadata import validate_release_metadata

compatibility_version_module = importlib.import_module("auralis.__version__")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_FILES = (
    PROJECT_ROOT / "package.json",
    PROJECT_ROOT / "auralis-web/frontend/package.json",
    PROJECT_ROOT / "desktop/package.json",
)


def test_dependency_free_release_preflight_passes() -> None:
    assert validate_release_metadata(product_version.__version__) == []


def test_dependency_free_release_preflight_rejects_wrong_version() -> None:
    errors = validate_release_metadata("9.9.9")
    assert any("does not match canonical version" in error for error in errors)


def test_all_release_metadata_matches_product_version() -> None:
    expected = product_version.__version__

    assert compatibility_version_module.__version__ == expected
    for package_file in PACKAGE_FILES:
        package = json.loads(package_file.read_text())
        assert package["version"] == expected, package_file

    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == expected

    health_source = (
        PROJECT_ROOT / "auralis-web/backend/routers/health.py"
    ).read_text()
    fallback = re.search(
        r"VersionInfoResponse\(\s*version=\"([^\"]+)\"",
        health_source,
        re.DOTALL,
    )
    assert fallback is not None
    assert fallback.group(1) == expected

    fallback_build_date = re.search(
        r'VersionInfoResponse\(.*?build_date="([^"]+)"',
        health_source,
        re.DOTALL,
    )
    assert fallback_build_date is not None
    assert fallback_build_date.group(1) == product_version.__build_date__

    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
    container_label = re.search(r'^LABEL version="([^"]+)"$', dockerfile, re.MULTILINE)
    assert container_label is not None
    assert container_label.group(1) == expected


def test_version_components_match_semantic_version() -> None:
    match = re.fullmatch(
        r"(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?",
        product_version.__version__,
    )
    assert match is not None

    major, minor, patch, prerelease_type, prerelease_number = match.groups()
    expected_core = (int(major), int(minor), int(patch))
    assert product_version.__version_info__[:3] == expected_core
    assert compatibility_version_module.__version_info__[:3] == expected_core
    assert (
        product_version.VERSION_MAJOR,
        product_version.VERSION_MINOR,
        product_version.VERSION_PATCH,
    ) == expected_core

    expected_prerelease = (
        f"{prerelease_type}.{prerelease_number}" if prerelease_type else ""
    )
    assert product_version.VERSION_PRERELEASE == expected_prerelease
