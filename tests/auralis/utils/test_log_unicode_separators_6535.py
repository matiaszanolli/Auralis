"""Unicode line separators and bidi controls are escaped in log values (#6535).

sanitize_log_value escaped C0, DEL and C1 only. U+2028/U+2029 are line breaks
to editors and str.splitlines(), and the bidi embedding/override/isolate
controls visually reorder the rest of a line; track tags and filenames are
logged through this function.
"""

import pytest

from auralis.utils.logging import sanitize_log_value

ADDED = [*range(0x200B, 0x2010), 0x2028, 0x2029, *range(0x202A, 0x202F), *range(0x2066, 0x206A)]


@pytest.mark.parametrize("code", ADDED, ids=[f"U+{c:04X}" for c in ADDED])
def test_each_added_character_is_escaped(code):
    out = sanitize_log_value(f"title{chr(code)}rest")

    assert chr(code) not in out
    assert out == f"title\\u{code:04x}rest"


def test_a_separator_no_longer_splits_the_logged_line():
    assert len(sanitize_log_value("Song\u2028[ERROR] forged").splitlines()) == 1


def test_byte_range_controls_keep_their_short_form_and_ordinary_text_is_untouched():
    assert sanitize_log_value("a\nb\x85c") == "a\\x0ab\\x85c"
    assert sanitize_log_value("Björk \u2013 Jóga ♪ 日本") == "Björk \u2013 Jóga ♪ 日本"
