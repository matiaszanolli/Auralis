"""Auralis Backend API version information."""

from typing import Any

# Import version from main auralis package
from auralis.__version__ import __db_schema_version__, __version__, __version_info__

# Backend API version
API_VERSION = __version__
API_VERSION_INFO = __version_info__

# Minimum client version required to connect to this backend
MIN_CLIENT_VERSION = "1.0.0"

# Database schema version
DB_SCHEMA_VERSION = __db_schema_version__


def get_version_info() -> dict[str, Any]:
    """
    Get comprehensive version information.

    Returns:
        Dictionary with version details
    """
    return {
        "api_version": API_VERSION,
        "api_version_info": {
            "major": API_VERSION_INFO[0],
            "minor": API_VERSION_INFO[1],
            "patch": API_VERSION_INFO[2],
        },
        "db_schema_version": DB_SCHEMA_VERSION,
        "min_client_version": MIN_CLIENT_VERSION,
    }
