"""
An embedded NUL byte is a PathValidationError, not a bare ValueError (#6159)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Path.resolve()`` raises ``ValueError("embedded null character in path")`` on
Python 3.14, and both validators caught only ``(OSError, RuntimeError)``. It
failed closed, but every ``except PathValidationError`` caller missed it, so the
request got a 500 with a traceback and ``_logs_rejections`` recorded nothing.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from security.path_errors import PathValidationError  # noqa: E402
from security.path_security import validate_file_path, validate_user_chosen_directory  # noqa: E402


def test_validate_file_path_rejects_a_nul_byte():
    with pytest.raises(PathValidationError):
        validate_file_path("/x\0.mp3")


def test_validate_user_chosen_directory_rejects_a_nul_byte(tmp_path):
    with pytest.raises(PathValidationError):
        validate_user_chosen_directory(str(tmp_path) + "\0suffix")


def test_nul_byte_rejection_is_logged(caplog):
    with caplog.at_level(logging.WARNING, logger="security.path_security"):
        with pytest.raises(PathValidationError):
            validate_file_path("/x\0.mp3")

    assert [r for r in caplog.records if "rejected" in r.getMessage().lower()]
