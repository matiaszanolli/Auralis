"""A missing-file rejection logs the file name, not the absolute path, at WARNING (#6189).

PathMissingError (a moved file, an unplugged drive: the commonest desktop failure) put the full path into the
WARNING that the #4925 wrapper persists to main.log, which users paste into public issues. The WARNING now keeps
the name; the full text is DEBUG. A containment rejection's message is already path-free and is logged unchanged.
"""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from security.path_errors import PathMissingError, PathValidationError  # noqa: E402
from security.path_security import validate_file_path  # noqa: E402


def _warnings(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


def test_a_missing_file_warns_with_the_name_only(tmp_path, caplog):
    missing = tmp_path / "Music" / "Band" / "gone.mp3"
    missing.parent.mkdir(parents=True)

    with caplog.at_level(logging.DEBUG), pytest.raises(PathMissingError):
        validate_file_path(str(missing), allowed_base_dirs=[tmp_path])

    assert "gone.mp3" in _warnings(caplog)
    assert str(tmp_path) not in _warnings(caplog)
    assert str(missing) in caplog.text  # the full path is still recoverable at DEBUG


def test_a_containment_rejection_is_logged_unchanged(tmp_path, caplog):
    outside = tmp_path / "elsewhere" / "x.mp3"
    allowed = tmp_path / "lib"
    allowed.mkdir()

    with caplog.at_level(logging.WARNING), pytest.raises(PathValidationError) as raised:
        validate_file_path(str(outside), allowed_base_dirs=[allowed])

    assert not isinstance(raised.value, PathMissingError)
    assert raised.value.log_text() == str(raised.value)
    assert "outside allowed directories" in _warnings(caplog)  # still traceable, and path-free already
