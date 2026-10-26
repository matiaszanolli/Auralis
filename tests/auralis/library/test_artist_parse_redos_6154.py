"""
parse_featured_artists is linear on hostile tags (#6154)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``\\s+``-led featuring patterns ran over the raw, untruncated artist tag and
were quadratic on a long whitespace run, holding the GIL for seconds to hours.
The string is now bounded and whitespace-collapsed before any regex runs, and
the extractor caps every string tag.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import time

import pytest

from auralis.library.scanner.metadata_extractor import MAX_TAG_TEXT_CHARS, MetadataExtractor
from auralis.library.utils.artist_normalizer import parse_featured_artists


@pytest.mark.parametrize("pad", [" ", "\t", " \n"])
def test_long_whitespace_run_returns_quickly(pad):
    hostile = "a" + pad * 200_000 + "b"

    started = time.perf_counter()
    result = parse_featured_artists(hostile)

    assert time.perf_counter() - started < 0.1
    assert result == ["a"]


def test_long_run_inside_a_featuring_credit_returns_quickly():
    hostile = "a" + " " * 200_000 + "feat." + " " * 200_000 + "b"

    started = time.perf_counter()
    parse_featured_artists(hostile)

    assert time.perf_counter() - started < 0.1


@pytest.mark.parametrize(
    "tag, expected",
    [
        ("Artist A feat. Artist B", ["Artist A", "Artist B"]),
        ("Artist A vs Artist B", ["Artist A", "Artist B"]),
        ("Artist A featuring Artist B & Artist C", ["Artist A", "Artist B", "Artist C"]),
        ("Simon & Garfunkel", ["Simon & Garfunkel"]),
        ("Tom Petty and the Heartbreakers", ["Tom Petty and the Heartbreakers"]),
        ("", ["Unknown Artist"]),
    ],
)
def test_normal_tags_parse_as_before(tag, expected):
    assert parse_featured_artists(tag) == expected


def test_extractor_caps_string_tags_but_not_numbers():
    extractor = MetadataExtractor()

    assert len(extractor._normalize_field_value("album", "x" * 1_000_000)) == MAX_TAG_TEXT_CHARS
    assert extractor._normalize_field_value("track", "7/12") == 7
