"""Mono input is DC-blocked once, not as a stacked stereo copy (#6717).

validate_and_normalize_input stacked a mono input to (N, 2), ran np.allclose
over it (full-size temporaries) and then remove_dc copied it again: three
stereo buffers for a mono input. remove_dc_dual_mono filters the channel once
and writes it to both. It must match remove_dc in values and memory layout,
since later whole-buffer reductions sum in memory order.
"""

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.hybrid_stage_dispatch import validate_and_normalize_input
from auralis.dsp.dc_blocker import remove_dc, remove_dc_dual_mono


@pytest.mark.parametrize("dtype", [np.float64, np.float32])
@pytest.mark.parametrize("n", [1024, 44_100])
def test_dual_mono_matches_remove_dc_of_the_stacked_input_exactly(dtype, n):
    mono = (0.2 * np.random.default_rng(n).standard_normal(n) + 0.01).astype(dtype)

    expected = remove_dc(np.column_stack([mono, mono]), 44_100)
    actual = remove_dc_dual_mono(mono, 44_100)

    assert actual.dtype == expected.dtype and actual.shape == expected.shape
    assert actual.strides == expected.strides  # same layout, so reductions sum in the same order
    np.testing.assert_array_equal(actual, expected)


def test_mono_input_normalizes_to_what_the_stacked_path_produced():
    processor = HybridProcessor(UnifiedConfig())
    mono = 0.1 * np.random.default_rng(3).standard_normal(44_100)

    normalized, early = validate_and_normalize_input(processor, mono)

    assert early is None
    np.testing.assert_array_equal(normalized, remove_dc(np.column_stack([mono, mono]), 44_100))


@pytest.mark.parametrize("level", [0.0, 1e-11, -1e-10, 1e-10])
def test_digital_silence_is_still_returned_unprocessed(level):
    processor = HybridProcessor(UnifiedConfig())
    silent = np.full((4096, 2), level)

    _, early = validate_and_normalize_input(processor, silent)

    assert isinstance(early, np.ndarray) and np.array_equal(early, silent)  # handed back untouched


def test_a_level_just_above_the_silence_tolerance_is_processed():
    processor = HybridProcessor(UnifiedConfig())
    _, early = validate_and_normalize_input(processor, np.full((4096, 2), 1.0000001e-10))
    assert early is None
