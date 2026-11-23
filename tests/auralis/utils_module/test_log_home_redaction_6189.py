"""
The user's home directory never reaches persisted logs (#6189)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A path under $HOME carries the OS account name and install layout, and an OSError's own text
(``[Errno 13] ... '/home/alice/...'``) embeds it where no call site can strip it. The central log
sanitizer, which every message, %-arg and traceback summary line already passes through, now
renders the home directory as ``~``.
"""

import logging
from pathlib import Path

import pytest

from auralis.utils import logging as alog


@pytest.fixture
def fake_home(monkeypatch):
    monkeypatch.setattr(alog, "_HOME_PREFIXES", ("/home/alice",))


def test_a_path_under_home_is_shortened(fake_home):
    assert alog.sanitize_log_value("failed on /home/alice/Music/a.flac") == "failed on ~/Music/a.flac"


def test_an_exception_message_that_embeds_a_path_is_redacted(fake_home):
    exc = PermissionError(13, "Permission denied", "/home/alice/Music/a.flac")
    assert "alice" not in alog.sanitize_log_value(exc)


def test_paths_outside_home_are_untouched(fake_home):
    assert alog.sanitize_log_value("/mnt/Musica/a.flac") == "/mnt/Musica/a.flac"


def test_a_missing_or_root_home_redacts_nothing(monkeypatch):
    monkeypatch.setattr(alog, "_HOME_PREFIXES", ())
    assert alog.sanitize_log_value("/home/alice/x") == "/home/alice/x"


def test_logging_calls_and_percent_args_go_through_it(fake_home, caplog):
    logger = logging.getLogger("home-redaction")
    with caplog.at_level(logging.WARNING, logger="home-redaction"):
        logger.warning("opened %s and /home/alice/b.flac", Path("/home/alice/a.flac"))

    assert "alice" not in caplog.text
    assert "~/a.flac" in caplog.text and "~/b.flac" in caplog.text


def test_a_traceback_summary_line_is_redacted(fake_home):
    try:
        raise OSError("cannot read /home/alice/a.flac")
    except OSError as exc:
        text = alog.SanitizingFormatter().formatException((type(exc), exc, exc.__traceback__))

    assert "cannot read ~/a.flac" in text
