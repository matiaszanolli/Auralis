"""
Auralis version information.
Single source of truth for version across the entire project.
"""

from typing import Any

__version__ = "1.2.1-beta.2"
__version_info__ = (1, 2, 1, "beta", 2)
__build_date__ = "2026-03-23"
__git_commit__ = ""  # Auto-populated during build

# Version components for programmatic access
VERSION_MAJOR = 1
VERSION_MINOR = 2
VERSION_PATCH = 1
VERSION_PRERELEASE = "beta.2"  # Empty string for stable releases
VERSION_BUILD = ""  # Optional build metadata

# Semantic version string
SEMANTIC_VERSION = __version__

# User-friendly display version
DISPLAY_VERSION = f"Auralis v{__version__}"

# Database schema version (independent of app version). The live, authoritative
# value lives in auralis/__version__.py (used by the migration manager); mirror
# it here instead of hardcoding so this never drifts again (#4054).
from auralis.__version__ import __db_schema_version__ as DB_SCHEMA_VERSION  # noqa: E402


def get_version() -> str:
    """Get the current version string."""
    return __version__


def get_version_info() -> dict[str, Any]:
    """
    Get detailed version information.

    Returns:
        Dictionary containing:
        - version: Full version string
        - major: Major version number
        - minor: Minor version number
        - patch: Patch version number
        - prerelease: Prerelease identifier (empty for stable)
        - build: Build metadata (empty if not set)
        - build_date: Build date
        - git_commit: Git commit hash (empty if not set)
        - api_version: API version string
        - db_schema_version: Database schema version
        - display: User-friendly display string
    """
    return {
        "version": __version__,
        "major": VERSION_MAJOR,
        "minor": VERSION_MINOR,
        "patch": VERSION_PATCH,
        "prerelease": VERSION_PRERELEASE,
        "build": VERSION_BUILD,
        "build_date": __build_date__,
        "git_commit": __git_commit__,
        "db_schema_version": DB_SCHEMA_VERSION,
        "display": DISPLAY_VERSION,
    }


def is_prerelease() -> bool:
    """Check if this is a prerelease version."""
    return bool(VERSION_PRERELEASE)


def is_beta() -> bool:
    """Check if this is a beta release."""
    return "beta" in VERSION_PRERELEASE.lower()


def is_rc() -> bool:
    """Check if this is a release candidate."""
    return "rc" in VERSION_PRERELEASE.lower()


def get_short_version() -> str:
    """Get short version without prerelease/build info."""
    return f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"


if __name__ == "__main__":
    # Print version info when run directly
    import json
    print(json.dumps(get_version_info(), indent=2))
