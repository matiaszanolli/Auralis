"""Changes to the file-access allowlist are logged (#6185).

register / unregister / clear are the only runtime widening and narrowing of
``validate_file_path``; only rejections were logged, so a folder added or the
whole list cleared left no trace.
"""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from security import path_allowlist  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_allowlist():
    saved = list(path_allowlist._extra_allowed_dirs)
    path_allowlist._extra_allowed_dirs.clear()
    yield
    path_allowlist._extra_allowed_dirs[:] = saved


def _messages(caplog):
    return [r.getMessage() for r in caplog.records if r.name == path_allowlist.logger.name]


def test_register_logs_the_folder_name_not_the_absolute_path(tmp_path, caplog):
    folder = tmp_path / "Albums"
    folder.mkdir()

    with caplog.at_level(logging.INFO, logger=path_allowlist.logger.name):
        path_allowlist.register_allowed_directory(folder)

    [message] = _messages(caplog)
    assert "registered" in message and "Albums" in message
    assert str(tmp_path) not in message  # absolute paths stay out of persisted logs (#5990)


def test_registering_twice_logs_once(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger=path_allowlist.logger.name):
        path_allowlist.register_allowed_directory(tmp_path)
        path_allowlist.register_allowed_directory(tmp_path)

    assert len(_messages(caplog)) == 1


def test_unregister_and_clear_are_logged(tmp_path, caplog):
    path_allowlist.register_allowed_directory(tmp_path)

    with caplog.at_level(logging.INFO, logger=path_allowlist.logger.name):
        path_allowlist.unregister_allowed_directory(tmp_path)
        path_allowlist.register_allowed_directory(tmp_path)
        path_allowlist.clear_extra_allowed_directories()

    messages = _messages(caplog)
    assert any("removed" in m for m in messages)
    assert any(m.startswith("Cleared 1 extra") for m in messages)
