"""Logged paths under a symlinked HOME are redacted, and no rejection logs an absolute path (#6537).

Home redaction compared against HOME as spelled, but validators log resolved paths: under a
symlinked home (Fedora Silverblue's /home -> /var/home) those start with the real target, so the
username and layout reached the persisted log. And only PathMissingError reduced its path to a file
name; the unreadable / not-a-directory / OS-error messages logged the full path.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.utils import logging as alog  # noqa: E402
from security.path_errors import PathMissingError, PathValidationError  # noqa: E402


def test_a_resolved_path_under_a_symlinked_home_is_redacted(tmp_path, monkeypatch):
    real_home = tmp_path / "var" / "home" / "alice"
    (real_home / "Music").mkdir(parents=True)
    (tmp_path / "home").symlink_to(tmp_path / "var" / "home")
    monkeypatch.setenv("HOME", str(tmp_path / "home" / "alice"))
    monkeypatch.setattr(alog, "_HOME_PREFIXES", alog._home_prefixes())

    track = Path.home() / "Music" / "x.flac"

    assert alog.sanitize_log_value(track) == "~/Music/x.flac"
    assert alog.sanitize_log_value(track.resolve()) == "~/Music/x.flac"


@pytest.mark.parametrize("message, logged", [
    ("File is not readable: /var/home/alice/Music/a b.flac", "File is not readable: a b.flac"),
    ("Path is not a directory: /var/home/alice/Music/a.flac", "Path is not a directory: a.flac"),
    ("Directory is not readable: /srv/alice/Music/", "Directory is not readable: Music"),
    ("Failed to resolve path: [Errno 36] File name too long: '/srv/alice/x'",
     "Failed to resolve path: [Errno 36] File name too long: 'x'"),
    ("Invalid directory path '/srv/alice': Directory does not exist: /srv/alice",
     "Invalid directory path 'alice': Directory does not exist: alice"),
    ("Path is outside allowed directories", "Path is outside allowed directories"),
])
def test_no_validation_error_logs_an_absolute_path(message, logged):
    assert PathValidationError(message).log_text() == logged


def test_missing_file_messages_keep_their_file_name_form():
    assert PathMissingError("File does not exist: /srv/alice/Music/x.flac").log_text() == "File does not exist: x.flac"
