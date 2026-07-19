"""
Tests for log-value sanitization (#4363)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Untrusted track metadata / upload filenames are interpolated into log lines. An
embedded CR/LF can forge additional log lines; terminal control sequences can
corrupt a log viewer. sanitize_log_value escapes those to a single safe line.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from auralis.utils.logging import sanitize_log_value


def test_newline_is_escaped_no_forged_line():
    """A CR/LF-bearing tag must not produce multiple log lines."""
    forged = "Foo\r\n2026-07-12 WARNING Fingerprint DB wiped"
    out = sanitize_log_value(forged)
    assert "\n" not in out
    assert "\r" not in out
    assert "\\x0d" in out and "\\x0a" in out  # CR and LF escaped
    assert out.count("\n") == 0  # single line


def test_bare_newline_escaped():
    out = sanitize_log_value("line1\nline2")
    assert "\n" not in out
    assert out == "line1\\x0aline2"


def test_terminal_control_sequence_escaped():
    """ESC-based color/control sequences are neutralized."""
    out = sanitize_log_value("\x1b[31mred\x1b[0m")
    assert "\x1b" not in out
    assert out.startswith("\\x1b")


def test_clean_value_passes_through_unchanged():
    """Ordinary (incl. non-ASCII printable) text is untouched — no over-escaping."""
    clean = "Café Tacvba — Río"
    assert sanitize_log_value(clean) == clean


def test_tab_is_preserved():
    """Tab (0x09) is allowed; only line-breaking / non-printable controls escape."""
    assert sanitize_log_value("a\tb") == "a\tb"


def test_del_and_c1_controls_escaped():
    assert sanitize_log_value("a\x7fb") == "a\\x7fb"      # DEL
    assert sanitize_log_value("a\x85b") == "a\\x85b"      # C1 (NEL)


def test_non_str_is_coerced():
    assert sanitize_log_value(12345) == "12345"
    assert sanitize_log_value(None) == "None"


def test_long_value_is_truncated():
    out = sanitize_log_value("x" * 600)
    assert len(out) == 501  # 500 chars + ellipsis
    assert out.endswith("…")


def test_truncation_happens_before_escaping_bounds_output():
    """A megabyte of newlines can't blow up the escaped output size."""
    out = sanitize_log_value("\n" * 10000)
    # 500 newlines each -> '\x0a' (4 chars) + ellipsis; bounded, single line.
    assert "\n" not in out
    assert len(out) <= 500 * 4 + 1
