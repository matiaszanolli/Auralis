# -*- coding: utf-8 -*-

"""
Genre EQ curves must not be aliased or integer-truncated (#4923)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two defects in the same function pair, which **masked each other**:

1. `generate_genre_eq_curve` returned a NumPy *view* into the module-level
   `GENRE_CURVES` table (slicing 25 of 25 bands does not copy), and
   `create_target_curve` mutated that view in place — writing its
   brightness/warmth adjustments straight into the shared preset, where they
   accumulated for the life of the process.

2. `GENRE_CURVES` entries were built from Python ints, so `dtype=int64`, and
   `curve[i] += 0.12` truncated to `+= 0`.

The masking matters for how this is tested. With the issue's own reproduction
(`brightness=0.3`) every increment is under 1.0 and truncates to zero, so the
table appears intact and the corruption is invisible. It only shows once the
increments clear 1.0 — hence `brightness=1.0` below. Fixing the dtype alone
would have UNMASKED the aliasing and made the corruption worse than it was.

It also invalidates the issue's suggested assertion "call twice, assert the two
results are identical". On the buggy code that passes — both calls return views
of the same corrupted buffer, so they are identical *because* of the bug. These
tests assert against `GENRE_CURVES` itself and against memory independence.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.dsp.eq.curves import (
    GENRE_CURVES,
    create_target_curve,
    generate_genre_eq_curve,
)


@pytest.fixture(autouse=True)
def _table_is_pristine():
    """Fail loudly if any test leaves the shared table mutated."""
    before = {genre: curve.copy() for genre, curve in GENRE_CURVES.items()}
    yield
    for genre, original in before.items():
        np.testing.assert_array_equal(
            GENRE_CURVES[genre], original,
            err_msg=f"GENRE_CURVES[{genre!r}] was mutated by a test (#4923)",
        )


class TestNoAliasing:
    def test_returned_curve_does_not_share_memory_with_the_table(self):
        """The core defect: 25-of-25 slicing is a view, not a copy."""
        curve = generate_genre_eq_curve('rock', num_bands=25)
        assert not np.shares_memory(curve, GENRE_CURVES['rock'])

    def test_mutating_the_result_leaves_the_table_intact(self):
        pristine = GENRE_CURVES['rock'].copy()

        curve = generate_genre_eq_curve('rock', num_bands=25)
        curve += 99.0

        np.testing.assert_array_equal(GENRE_CURVES['rock'], pristine)

    def test_create_target_curve_does_not_accumulate_across_calls(self):
        """brightness=1.0, not 0.3: below 1.0 the int truncation hid this."""
        pristine = GENRE_CURVES['rock'].copy()

        first = create_target_curve('rock', brightness=1.0)
        second = create_target_curve('rock', brightness=1.0)

        np.testing.assert_array_equal(GENRE_CURVES['rock'], pristine)
        np.testing.assert_allclose(first, second)
        # Equal in value but distinct buffers — the old code satisfied the
        # first assertion while failing this one.
        assert not np.shares_memory(first, second)

    def test_every_genre_is_independent(self):
        """SIBLING: the aliasing was per-entry, not specific to 'rock'."""
        for genre in GENRE_CURVES:
            curve = generate_genre_eq_curve(genre, num_bands=25)
            assert not np.shares_memory(curve, GENRE_CURVES[genre]), genre


class TestNoIntegerTruncation:
    def test_table_is_floating_point(self):
        for genre, curve in GENRE_CURVES.items():
            assert np.issubdtype(curve.dtype, np.floating), f"{genre}: {curve.dtype}"

    def test_sub_one_db_brightness_survives(self):
        """band 5 of 25 at brightness=0.3 -> +0.12 dB, previously +0."""
        base = GENRE_CURVES['rock'][5]
        curve = create_target_curve('rock', brightness=0.3)

        expected = base + 0.3 * 2.0 * (5 / 25)
        assert curve[5] == pytest.approx(expected)
        assert curve[5] != pytest.approx(base), "adjustment truncated away"

    def test_sub_one_db_warmth_survives(self):
        base = GENRE_CURVES['jazz'][10]
        curve = create_target_curve('jazz', warmth=0.2)

        expected = base + 0.2 * 2.0 * (1.0 - abs(10 / 25 - 0.3))
        assert curve[10] == pytest.approx(expected)

    def test_generated_curve_is_float_for_every_genre(self):
        for genre in GENRE_CURVES:
            assert np.issubdtype(
                generate_genre_eq_curve(genre).dtype, np.floating
            ), genre


class TestReadOnlyGuard:
    """Defence in depth: a future edit dropping the `.copy()` must fail loudly
    rather than silently corrupting process-global state again."""

    def test_table_entries_reject_in_place_writes(self):
        with pytest.raises(ValueError, match="read-only"):
            GENRE_CURVES['rock'][0] = 99.0

    def test_reads_and_copies_still_work(self):
        # The guard must not break legitimate use.
        assert float(GENRE_CURVES['rock'][0]) == 2.0
        copy = GENRE_CURVES['rock'].copy()
        copy[0] = 99.0
        assert copy.flags.writeable


class TestUnchangedBehaviour:
    """The safe branches must keep working — they were never the bug."""

    def test_padding_branch_still_pads(self):
        curve = generate_genre_eq_curve('rock', num_bands=30)
        assert len(curve) == 30
        np.testing.assert_array_equal(curve[25:], np.zeros(5))

    def test_truncating_branch_still_truncates(self):
        curve = generate_genre_eq_curve('rock', num_bands=10)
        assert len(curve) == 10
        np.testing.assert_array_equal(curve, GENRE_CURVES['rock'][:10])

    def test_unknown_genre_is_flat(self):
        np.testing.assert_array_equal(
            generate_genre_eq_curve('nonexistent-genre'), np.zeros(25)
        )

    def test_no_genre_path_unaffected(self):
        curve = create_target_curve(brightness=0.3)
        assert curve[5] == pytest.approx(0.3 * 2.0 * (5 / 25))
