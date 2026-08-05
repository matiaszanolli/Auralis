"""
Regression test: log sanitization applied centrally, not per-site (#4828)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#4363 fixed log injection only at the 4 files/14 sites that explicitly called
sanitize_log_value(). Dozens of other sites — across auralis/ (via this
module's debug/info/warning/error) and auralis-web/backend/ (via stdlib
`logging.getLogger(__name__)`) — never opted in. Sanitization is now applied
centrally so no call site has to remember to opt in:
  - debug/info/warning/error escape their message before formatting.
  - a LogRecordFactory wrapper escapes every stdlib `logging` record's
    msg/args (covers both f-string and %-style logging).

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import io
import logging

import auralis.utils.logging as alog


def test_custom_logger_functions_sanitize_forged_newlines():
    """debug/info/warning/error must not let \\r\\n reach the handler unescaped."""
    captured: list[str] = []
    alog.set_log_handler(captured.append)
    try:
        forged = "Foo\r\n2026-01-01 WARNING Fingerprint DB wiped"
        alog.info(forged)
        alog.debug(forged)
        alog.warning(forged)
        alog.error(forged)
    finally:
        alog.set_log_handler(None)

    for line in captured:
        assert "\r" not in line and "\n" not in line
        assert "\\x0d" in line and "\\x0a" in line


def test_stdlib_logging_fstring_site_is_sanitized():
    """A backend-style logger.info(f"...") call (no explicit sanitize) is covered."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("test_log_sanitize_central_4828_fstring")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    try:
        filename = "evil\r\nFORGED: fake admin action performed"
        logger.info(f"Loading {filename}")
    finally:
        logger.removeHandler(handler)

    out = stream.getvalue()
    assert "\r\n" not in out
    assert "\\x0d\\x0a" in out


def test_stdlib_logging_percent_style_args_are_sanitized():
    """%-style logging (logger.info("...%s", value)) sanitizes the interpolated arg."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("test_log_sanitize_central_4828_percent")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.info("Loading %s", "evil\r\nFORGED: fake admin action performed")
    finally:
        logger.removeHandler(handler)

    out = stream.getvalue()
    assert "\r\n" not in out
    assert "\\x0d\\x0a" in out


def test_already_sanitized_value_is_not_double_escaped():
    """Sites that already call sanitize_log_value() explicitly (#4363) stay correct."""
    from auralis.utils.logging import sanitize_log_value

    pre_sanitized = sanitize_log_value("evil\r\nname")
    assert pre_sanitized == "evil\\x0d\\x0aname"

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("test_log_sanitize_central_4828_idempotent")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.info(f"Artist: {pre_sanitized}")
    finally:
        logger.removeHandler(handler)

    # Backslashes/x/digits are printable — re-sanitizing is a no-op, so the
    # already-escaped text passes through unchanged (no double-escaping).
    assert stream.getvalue().strip() == f"Artist: {pre_sanitized}"
