# -*- coding: utf-8 -*-

"""
Auralis Helper Functions
~~~~~~~~~~~~~~~~~~~~~~~~

General utility functions

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""

import tempfile
import os
from typing import Any


def get_temp_folder(results: Any) -> str:
    """
    Get a temporary folder for processing

    Args:
        results: List of result objects

    Returns:
        str: Path to temporary folder
    """
    return tempfile.gettempdir()


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        str: Formatted duration string (e.g., "2h 30m 45s")
    """
    if seconds < 0:
        return "0s"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def format_filesize(bytes_size: int) -> str:
    """
    Format file size in bytes to human-readable string.

    Args:
        bytes_size: Size in bytes

    Returns:
        str: Formatted size string (e.g., "1.5 GB")
    """
    if bytes_size < 0:
        return "0 B"

    size: float = float(bytes_size)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0

    return f"{size:.1f} PB"