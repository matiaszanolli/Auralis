"""
Regression test: path validators log success at DEBUG, not INFO (#3844)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The path validators run very frequently (validate_file_path 5× per metadata
request) and previously logged the full resolved absolute path at INFO. That
flooded the logs and persisted the user's media-library layout to disk via
electron-log. The success lines are now DEBUG so absolute paths no longer
appear at INFO in normal operation.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from security.path_security import (
    validate_file_path,
    validate_user_chosen_directory,
)

LOGGER_NAME = "security.path_security"


def test_user_chosen_directory_success_not_logged_at_info(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        result = validate_user_chosen_directory(str(tmp_path))

    assert result is not None
    info_plus = [r for r in caplog.records if r.levelno >= logging.INFO]
    assert not any("validated" in r.getMessage().lower() for r in info_plus), (
        "Directory-validation success must not be logged at INFO (it leaks the path)"
    )


def test_user_chosen_directory_success_is_logged_at_debug(tmp_path, caplog):
    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        validate_user_chosen_directory(str(tmp_path))

    debug_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("validated" in m.lower() for m in debug_msgs), (
        "Success should still be available at DEBUG for troubleshooting"
    )


def test_file_path_success_not_logged_at_info(tmp_path, caplog):
    f = tmp_path / "song.mp3"
    f.write_bytes(b"\x00\x01")

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        result = validate_file_path(str(f), allowed_base_dirs=[tmp_path])

    assert result is not None
    info_plus = [r for r in caplog.records if r.levelno >= logging.INFO]
    assert not any(
        "validation successful" in r.getMessage().lower() for r in info_plus
    ), "File-path validation success must not be logged at INFO"
