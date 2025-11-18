"""
Auralis version information.
Single source of truth for version across the entire project.
"""

__version__ = "1.1.0-beta.1"
__version_info__ = (1, 1, 0, "beta", 1)
__build_date__ = "2025-11-18"
__git_commit__ = ""  # Auto-populated during build

# Version components for programmatic access
VERSION_MAJOR = 1
VERSION_MINOR = 1
VERSION_PATCH = 0
VERSION_PRERELEASE = "beta.1"  # Empty string for stable releases
VERSION_BUILD = ""  # Optional build metadata

# Semantic version string
SEMANTIC_VERSION = __version__

# User-friendly display version
DISPLAY_VERSION = f"Auralis v{__version__}"

# API version (for backward compatibility)
API_VERSION = "v1"

# Database schema version (independent of app version)
DB_SCHEMA_VERSION = 3

# Minimum compatible version (for upgrades)
MIN_COMPATIBLE_VERSION = "0.9.0"


def get_version() -> str:
    """Get the current version string."""
    return __version__


def get_version_info() -> dict:
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
        "api_version": API_VERSION,
        "db_schema_version": DB_SCHEMA_VERSION,
        "display": DISPLAY_VERSION,
    }


def is_compatible(version: str) -> bool:
    """
    Check if a version is compatible with current version.

    Args:
        version: Version string to check (e.g., "0.9.0")

    Returns:
        True if version is compatible, False otherwise
    """
    try:
        from packaging.version import Version
        return Version(version) >= Version(MIN_COMPATIBLE_VERSION)
    except ImportError:
        # Fallback to simple string comparison if packaging not available
        return version >= MIN_COMPATIBLE_VERSION


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
