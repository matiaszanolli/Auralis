"""#5786 — every list of the 25 fingerprint dimension names derives from the schema.

The names were hand-copied in the normalizer, the quantizer, metrics/constants and
FingerprintService, next to DIMENSION_SCHEMA's "single source of truth" docstring,
and the tests only pinned ``len(...) == 25``. The vector order matters (quantizer,
normalizer, TrackFingerprint.to_vector()), so adding or reordering a dimension
meant five hand edits with no failing test.
"""

import pytest

from auralis.analysis.fingerprint import fingerprint_service, windowed_compute
from auralis.analysis.fingerprint.metrics.constants import FINGERPRINT_DIMENSION_NAMES
from auralis.analysis.fingerprint.normalizer import FingerprintNormalizer
from auralis.analysis.fingerprint.schema import (
    BAND_PCT_KEYS,
    DIMENSION_NAMES,
    DIMENSION_SCHEMA,
    band_pct_valid,
)
from auralis.core.processing.target_derivation import TARGET_FEATURES
from auralis.learning.reference_seeder import BAND_FIELDS
from auralis.library.fingerprint_quantizer import FingerprintQuantizer


def test_schema_names_are_the_schema_keys_in_order() -> None:
    assert DIMENSION_NAMES == tuple(DIMENSION_SCHEMA)
    assert len(DIMENSION_NAMES) == 25


def test_band_keys_are_the_seven_pct_dimensions() -> None:
    assert len(BAND_PCT_KEYS) == 7
    assert BAND_PCT_KEYS == DIMENSION_NAMES[:7]
    assert all(key.endswith('_pct') for key in BAND_PCT_KEYS)


@pytest.mark.parametrize(
    "copy",
    [
        pytest.param(list(FingerprintNormalizer.DIMENSION_NAMES), id="normalizer"),
        pytest.param(list(FingerprintQuantizer.DIMENSION_NAMES), id="quantizer"),
        pytest.param(list(fingerprint_service._FP_KEYS), id="fingerprint_service"),
    ],
)
def test_ordered_copies_equal_the_schema_order(copy: list[str]) -> None:
    assert copy == list(DIMENSION_NAMES)


def test_unordered_and_subset_copies_agree_with_the_schema() -> None:
    assert FINGERPRINT_DIMENSION_NAMES == frozenset(DIMENSION_NAMES)
    assert BAND_FIELDS == BAND_PCT_KEYS
    assert TARGET_FEATURES[:7] == BAND_PCT_KEYS
    assert set(TARGET_FEATURES) <= set(DIMENSION_NAMES)


def test_quantizer_has_bounds_for_every_dimension() -> None:
    assert set(FingerprintQuantizer.DIMENSION_BOUNDS) == set(DIMENSION_NAMES)


class TestBandPctValid:
    def test_accepts_sums_within_five_percent(self) -> None:
        for total in (0.95, 1.0, 1.05):
            fp = {key: total / 7 for key in BAND_PCT_KEYS}
            assert band_pct_valid(fp), total

    def test_rejects_sums_outside_the_tolerance(self) -> None:
        for total in (0.0, 0.9, 1.1, 2.0):
            fp = {key: total / 7 for key in BAND_PCT_KEYS}
            assert not band_pct_valid(fp), total

    def test_missing_keys_count_as_zero(self) -> None:
        assert not band_pct_valid({})


def test_there_is_one_band_check_and_no_dead_copy() -> None:
    assert not hasattr(fingerprint_service.FingerprintService, '_band_pct_valid')
    assert not hasattr(fingerprint_service.FingerprintService, '_numpy_to_python')
    # windowed_compute's own copy was never called; it is gone, not shared.
    assert not hasattr(windowed_compute, '_band_pct_valid')
    assert not hasattr(windowed_compute, '_BAND_PCT_KEYS')
    assert fingerprint_service.band_pct_valid is band_pct_valid
