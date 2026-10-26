"""
The engine logging facade reaches the stdlib "auralis" logger (#6156)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``debug/info/warning/error`` only emitted when ``set_log_handler`` had been
called, and no production code calls it, so every event from the scanner,
database, loaders and metadata backup was discarded. With no handler installed
they now delegate to ``logging.getLogger("auralis")``; a custom handler still
overrides that and ``set_log_handler(None)`` restores the bridge.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from auralis.utils.logging import debug, error, info, set_log_handler, warning


@pytest.fixture(autouse=True)
def _no_custom_handler():
    set_log_handler(None)
    yield
    set_log_handler(None)


@pytest.mark.parametrize(
    "emit, level",
    [(debug, logging.DEBUG), (info, logging.INFO), (warning, logging.WARNING), (error, logging.ERROR)],
)
def test_each_level_produces_a_record_on_the_auralis_logger(caplog, emit, level):
    with caplog.at_level(logging.DEBUG, logger="auralis"):
        emit("something happened")

    records = [r for r in caplog.records if r.name == "auralis"]
    assert [(r.levelno, r.getMessage()) for r in records] == [(level, "something happened")]


def test_messages_are_sanitised(caplog):
    with caplog.at_level(logging.WARNING, logger="auralis"):
        warning("tag\nERROR: forged line\x1b[31m")

    (record,) = [r for r in caplog.records if r.name == "auralis"]
    assert "\n" not in record.getMessage()
    assert "\x1b" not in record.getMessage()
    assert "forged line" in record.getMessage()


def test_record_is_attributed_to_the_caller_not_the_facade(caplog):
    with caplog.at_level(logging.WARNING, logger="auralis"):
        warning("where am I")

    (record,) = [r for r in caplog.records if r.name == "auralis"]
    assert record.funcName == "test_record_is_attributed_to_the_caller_not_the_facade"


def test_custom_handler_overrides_the_bridge_and_none_restores_it(caplog):
    received: list[str] = []
    set_log_handler(received.append)

    with caplog.at_level(logging.INFO, logger="auralis"):
        info("to the handler")
    assert received == ["INFO: to the handler"]
    assert not [r for r in caplog.records if r.name == "auralis"]

    set_log_handler(None)
    with caplog.at_level(logging.INFO, logger="auralis"):
        info("to stdlib")
    assert [r.getMessage() for r in caplog.records if r.name == "auralis"] == ["to stdlib"]


def test_failed_library_scan_is_visible_in_the_log(caplog, tmp_path):
    from auralis.library.scanner import LibraryScanner

    library = MagicMock()
    library.try_acquire_scan_slot.return_value = (True, 1)
    library.try_reserve_scan_paths.return_value = []
    scanner = LibraryScanner(library)
    with patch("auralis.library.scanner.scanner.count_audio_files", side_effect=RuntimeError("disk gone")), \
         caplog.at_level(logging.WARNING, logger="auralis"):
        scanner.scan_directories([str(tmp_path)])

    assert [r for r in caplog.records if "Library scan failed: disk gone" in r.getMessage()]
