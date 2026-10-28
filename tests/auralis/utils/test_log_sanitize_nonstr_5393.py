"""
Regression test: log sanitization covers non-str args and tracebacks (#5393)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The #4828 central sanitization sanitized record.msg and only *str* args. A
``Path`` or ``Exception`` arg (%s-style) passed through the factory untouched
and was str()-formatted later by getMessage(), after sanitization had already
run — and traceback text from exc_info/logger.exception() is rendered by the
handler's Formatter, which never went through sanitization at all. A cover-art
file with a crafted name (e.g. containing \\r\\n) could therefore forge log
lines in the persisted electron-log file.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import io
import logging
from pathlib import Path

import auralis.utils.logging as alog
from auralis.utils.logging import SanitizingFormatter, install_sanitizing_formatter

FORGED = "evil\r\n2026-01-01 ERROR FORGED: admin action performed"


def _capture(logger_name: str, formatter: logging.Formatter) -> tuple[logging.Logger, io.StringIO, logging.StreamHandler]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger, stream, handler


def test_path_arg_is_sanitized():
    """A %s-style Path arg is str()-coerced and escaped in the factory, not
    left opaque for getMessage() to interpolate after sanitization."""
    logger, stream, handler = _capture(
        "test_5393_path", logging.Formatter("%(message)s")
    )
    try:
        logger.info("Thumbnail generation failed for %s", Path(f"/music/{FORGED}"))
    finally:
        logger.removeHandler(handler)

    out = stream.getvalue()
    assert "\r" not in out and "\n" not in out.strip()
    assert "\\x0d\\x0a" in out


def test_exception_arg_is_sanitized():
    """A %s-style Exception arg (e.g. a loader error embedding a raw path)."""
    logger, stream, handler = _capture(
        "test_5393_exc", logging.Formatter("%(message)s")
    )
    try:
        logger.info("Loader failed: %s", ValueError(FORGED))
    finally:
        logger.removeHandler(handler)

    out = stream.getvalue()
    assert "\r" not in out
    assert "\\x0d\\x0a" in out


def test_numeric_args_keep_their_format_specifiers():
    """Numeric args must pass through as objects, or '%d' would raise
    TypeError against the sanitized *string* the factory substituted."""
    logger, stream, handler = _capture(
        "test_5393_numeric", logging.Formatter("%(message)s")
    )
    try:
        logger.info("Purged %d cached item(s) from %s", 5, Path("/tmp/thumbs"))
    finally:
        logger.removeHandler(handler)

    assert stream.getvalue() == "Purged 5 cached item(s) from /tmp/thumbs\n"


def test_dict_style_args_are_sanitized():
    """%(key)s-style args sanitize their values too."""
    logger, stream, handler = _capture(
        "test_5393_dict", logging.Formatter("%(message)s")
    )
    try:
        logger.info("Loading %(name)s", {"name": FORGED})
    finally:
        logger.removeHandler(handler)

    out = stream.getvalue()
    assert "\r" not in out
    assert "\\x0d\\x0a" in out


def test_traceback_text_is_sanitized_by_the_formatter():
    """exc_info text never passes through the record factory; the handler's
    Formatter must escape control characters inside it."""
    logger, stream, handler = _capture(
        "test_5393_tb", SanitizingFormatter("%(message)s")
    )
    try:
        try:
            raise ValueError(FORGED)
        except ValueError:
            logger.exception("Thumbnail generation failed for %s", Path("/music/cover.jpg"))
    finally:
        logger.removeHandler(handler)

    out = stream.getvalue()
    assert "\r" not in out
    assert "\\x0d\\x0a" in out
    # Real traceback line structure is preserved — the escape is per line,
    # so the rendered traceback is still multi-line and readable.
    assert "Traceback (most recent call last)" in out
    assert out.count("\n") >= 3


def test_plain_formatter_leaves_traceback_injection_open():
    """The vulnerability contrast: a plain Formatter renders the raw CR/LF —
    this is what install_sanitizing_formatter() exists to replace."""
    logger, stream, handler = _capture(
        "test_5393_plain", logging.Formatter("%(message)s")
    )
    try:
        try:
            raise ValueError(FORGED)
        except ValueError:
            logger.exception("failed")
    finally:
        logger.removeHandler(handler)

    assert "\r\n" in stream.getvalue()


def test_install_sanitizing_formatter_rewraps_existing_handlers():
    """install_sanitizing_formatter() swaps the formatter on handlers that
    already exist (basicConfig() creates plain ones and takes no class)."""
    logger, stream, handler = _capture(
        "test_5393_install", logging.Formatter("%(message)s")
    )
    try:
        install_sanitizing_formatter(logger, fmt="%(levelname)s: %(message)s")
        assert isinstance(handler.formatter, SanitizingFormatter)

        try:
            raise ValueError(FORGED)
        except ValueError:
            logger.exception("failed for %s", Path("/music/cover.jpg"))
    finally:
        logger.removeHandler(handler)

    out = stream.getvalue()
    assert out.startswith("ERROR: failed for /music/cover.jpg")
    assert "\r" not in out
    assert "\\x0d\\x0a" in out


def test_reused_format_string_when_fmt_omitted():
    """Without an explicit fmt, the handler's existing format string is kept."""
    logger, stream, handler = _capture(
        "test_5393_reuse", logging.Formatter("X %(message)s Y")
    )
    try:
        install_sanitizing_formatter(logger)
        logger.warning("plain message")
    finally:
        logger.removeHandler(handler)

    assert stream.getvalue() == "X plain message Y\n"


def test_traceback_frames_keep_their_own_lines_but_not_injected_ones():
    """#6161: sanitizing a whole formatted frame escaped its structural newlines,
    gluing every frame onto one line. Frames stay one per line (file line, then
    its source line) while a newline injected through a path or message is still
    escaped."""
    logger, stream, handler = _capture(
        "test_6161_tb", SanitizingFormatter("%(message)s")
    )

    def inner():
        raise ValueError(FORGED)

    def outer():
        inner()

    try:
        try:
            outer()
        except ValueError:
            logger.exception("boom")
    finally:
        logger.removeHandler(handler)

    lines = stream.getvalue().splitlines()
    file_lines = [ln for ln in lines if ln.startswith('  File "')]
    assert [ln.rsplit(", in ", 1)[1] for ln in file_lines][-2:] == ["outer", "inner"]
    assert "    outer()" in lines and "    inner()" in lines
    assert "\\x" not in "".join(file_lines)
    # the injected newline is still escaped, so no line starts with the forged text
    assert not any(ln.startswith("2026-01-01") for ln in lines)
    assert any("evil\\x0d\\x0a2026-01-01 ERROR FORGED" in ln for ln in lines)


def test_traceback_frame_filename_with_a_newline_cannot_forge_a_line():
    logger, stream, handler = _capture(
        "test_6161_name", SanitizingFormatter("%(message)s")
    )
    code = compile("raise ValueError('x')", "evil\n2026-01-01 ERROR FORGED", "exec")
    try:
        try:
            exec(code)
        except ValueError:
            logger.exception("boom")
    finally:
        logger.removeHandler(handler)

    lines = stream.getvalue().splitlines()
    assert not any(ln.startswith("2026-01-01") for ln in lines)
    assert any("evil\\x0a2026-01-01 ERROR FORGED" in ln for ln in lines)
