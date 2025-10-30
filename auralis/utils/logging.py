# -*- coding: utf-8 -*-

"""
Auralis Logging System
~~~~~~~~~~~~~~~~~~~~~~

Logging and debug utilities

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""


class Code:
    """Log message codes"""
    INFO_LOADING = "Loading audio files..."
    INFO_EXPORTING = "Exporting results..."
    INFO_COMPLETED = "Processing completed successfully"
    ERROR_VALIDATION = "Validation error"
    ERROR_LOADING = "Error loading audio file"
    ERROR_INVALID_AUDIO = "Invalid audio file format"
    ERROR_FILE_NOT_FOUND = "File not found"


class ModuleError(Exception):
    """Custom exception for module errors"""
    def __init__(self, code):
        self.code = code
        super().__init__(f"Module error: {code}")


# Global log handler and level
_log_handler = None
_log_level = "INFO"


def set_log_handler(handler):
    """Set the global log handler function"""
    global _log_handler
    _log_handler = handler


def set_log_level(level: str):
    """Set the global log level"""
    global _log_level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    if level.upper() in valid_levels:
        _log_level = level.upper()


def get_log_level() -> str:
    """Get the current log level"""
    return _log_level


def debug(message: str):
    """Log a debug message"""
    if _log_handler:
        _log_handler(f"DEBUG: {message}")


def info(message: str):
    """Log an info message"""
    if _log_handler:
        _log_handler(f"INFO: {message}")


def warning(message: str):
    """Log a warning message"""
    if _log_handler:
        _log_handler(f"WARNING: {message}")


def error(message: str):
    """Log an error message"""
    if _log_handler:
        _log_handler(f"ERROR: {message}")


def debug_line():
    """Log a debug separator line"""
    if _log_handler:
        _log_handler("-" * 50)