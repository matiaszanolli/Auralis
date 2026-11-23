"""Uncaught exceptions and warnings go through logging, so they are sanitized (#6540).

The sanitizer is the logging record factory plus formatter; the traceback of an uncaught
exception in a bare thread, and warnings.warn output, went straight to stderr, which the
Electron pipe persisted verbatim. route_uncaught_to_logging() routes all three through logging.
"""

import logging
import sys
import threading
import warnings

import pytest

from auralis.utils.log_formatter import SanitizingFormatter, route_uncaught_to_logging

NL = chr(10)
ESC = chr(27)


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(SanitizingFormatter("%(levelname)s %(name)s %(message)s"))
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))


@pytest.fixture
def captured(monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    handler = _Capture()
    root = logging.getLogger()
    root.addHandler(handler)
    route_uncaught_to_logging()
    yield handler
    logging.captureWarnings(False)
    root.removeHandler(handler)


def test_an_uncaught_thread_exception_is_logged_sanitized(captured):
    def worker():
        raise ValueError(f"bad tag{NL}2026-01-01 - x - ERROR - forged")

    thread = threading.Thread(target=worker, name="fingerprint-worker")
    thread.start()
    thread.join()

    record = next(line for line in captured.lines if "fingerprint-worker" in line)
    assert record.startswith("CRITICAL auralis.uncaught Uncaught exception in thread fingerprint-worker")
    assert "ValueError: bad tag\\x0a2026-01-01 - x - ERROR - forged" in record
    assert f"{NL}2026-01-01 - x - ERROR - forged" not in record


def test_a_warning_is_logged_sanitized(captured):
    warnings.warn(f"tag {ESC}[2J{NL}forged", UserWarning, stacklevel=1)

    record = next(line for line in captured.lines if "py.warnings" in line)
    assert "\\x1b[2J\\x0aforged" in record
    assert ESC not in record and NL not in record


def test_the_main_thread_hook_logs_and_leaves_ctrl_c_alone(captured, monkeypatch):
    seen = []
    monkeypatch.setattr(sys, "__excepthook__", lambda *exc: seen.append(exc[0]))

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)

    assert any(line.startswith("CRITICAL auralis.uncaught Uncaught exception") for line in captured.lines)
    assert seen == [KeyboardInterrupt]


def test_a_plain_handler_formatting_first_cannot_hand_over_its_unsanitized_traceback():
    try:
        raise ValueError(f"bad{NL}forged")
    except ValueError:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())

    plain = logging.Formatter("%(message)s").format(record)  # caches its rendering on the record
    sanitized = SanitizingFormatter("%(message)s").format(record)

    assert f"bad{NL}forged" in plain
    assert "ValueError: bad\\x0aforged" in sanitized and f"bad{NL}forged" not in sanitized
