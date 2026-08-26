"""#5222 — DynamicRangeAnalyzer._calculate_dr_value() implements real DR.

It used to return 95th-percentile block peak minus mean block RMS — a
crest-factor-like number on no particular scale — while everything reading it
(`_categorize_dynamic_range`'s 20/14/10/7/4 bands, `_assess_loudness_war`'s
`dr_value < 7`) is written against the TT/Pleasurize DR scale.
"""

import numpy as np
import pytest

from auralis.analysis.dynamic_range import DynamicRangeAnalyzer

SR = 44100
BLOCK = int(3.0 * SR)


def _block(amplitude: float, spike: float | None = None) -> np.ndarray:
    t = np.arange(BLOCK) / SR
    b = amplitude * np.sin(2 * np.pi * 440 * t)
    if spike is not None:
        b[BLOCK // 2] = spike
    return b


@pytest.fixture
def analyzer() -> DynamicRangeAnalyzer:
    return DynamicRangeAnalyzer(SR)


def test_known_peak_to_top20_rms_ratio(analyzer: DynamicRangeAnalyzer) -> None:
    """10 blocks, loudest 20% at RMS 0.5 with peaks at 1.0 -> DR = 6.02 dB.

    ``rms = sqrt(2 * mean(x**2))`` makes a 0.5-amplitude sine read 0.5, and
    peak2 (the second-highest block peak) is the 1.0 spike, so
    20*log10(1.0 / 0.5) = 6.02.
    """
    audio = np.concatenate(
        [_block(0.5, spike=1.0), _block(0.5, spike=1.0)]
        + [_block(0.05) for _ in range(8)]
    )
    assert analyzer._calculate_dr_value(audio) == pytest.approx(6.02, abs=0.02)


def test_steady_full_scale_sine_is_dr_zero(analyzer: DynamicRangeAnalyzer) -> None:
    """The factor 2 in the DR definition normalises a sine to 0 dB.

    A constant tone has no dynamic range; the old implementation reported its
    3 dB crest instead.
    """
    audio = np.tile(_block(1.0), 10)
    assert analyzer._calculate_dr_value(audio) == pytest.approx(0.0, abs=0.01)


def test_highest_peak_is_discarded(analyzer: DynamicRangeAnalyzer) -> None:
    """A single outlier tick must not inflate DR — peak2 is used, not peak1."""
    base = [_block(0.5, spike=1.0) for _ in range(10)]
    assert analyzer._calculate_dr_value(np.concatenate(base)) == pytest.approx(6.02, abs=0.02)

    # One block now peaks 4x higher than every other. Using the highest peak
    # would report 20*log10(4.0 / 0.5) = 18.06 dB; discarding it keeps 6.02.
    ticked = list(base)
    ticked[0] = _block(0.5, spike=4.0)

    assert analyzer._calculate_dr_value(np.concatenate(ticked)) == pytest.approx(6.02, abs=0.02)


def test_counts_every_whole_block(analyzer: DynamicRangeAnalyzer) -> None:
    """The final complete block must be counted.

    The old stride loop ran `range(0, len - block, block)`, so it never
    reached the last whole block. Here only the last two blocks carry the
    1.0 spikes, so peak2 is 1.0 (DR 6.02) when all six blocks are seen and
    0.5 (DR 0.0) if the final one is dropped.
    """
    audio = np.concatenate(
        [_block(0.5) for _ in range(4)] + [_block(0.5, spike=1.0) for _ in range(2)]
    )
    assert analyzer._calculate_dr_value(audio) == pytest.approx(6.02, abs=0.02)


def test_short_and_silent_input(analyzer: DynamicRangeAnalyzer) -> None:
    assert analyzer._calculate_dr_value(np.zeros(1000)) == 0.0
    assert analyzer._calculate_dr_value(np.zeros(BLOCK * 4)) == 0.0


def test_dr_never_negative(analyzer: DynamicRangeAnalyzer) -> None:
    audio = np.concatenate([_block(0.9) for _ in range(5)])
    assert analyzer._calculate_dr_value(audio) >= 0.0


def test_analyze_dynamic_range_still_reports_dr(analyzer: DynamicRangeAnalyzer) -> None:
    """The advisory-only contract is unchanged: same key, still a float."""
    audio = np.concatenate(
        [_block(0.5, spike=1.0), _block(0.5, spike=1.0)] + [_block(0.05) for _ in range(8)]
    )
    result = analyzer.analyze_dynamic_range(audio)

    assert isinstance(result["dr_value"], float)
    assert result["dr_value"] == pytest.approx(6.02, abs=0.02)
    assert result["dynamic_range_category"] == "Poor"  # DR 6 on the real scale
