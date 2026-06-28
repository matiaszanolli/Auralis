"""Regression: QualityMetrics resets per-track analyzer history (#4120, #4221).

QualityMetrics holds one DynamicRangeAnalyzer / PhaseCorrelationAnalyzer for the
lifetime of the instance and reuses them across tracks. Their history lists
(crest_history / correlation_history) must be reset at the start of each
assess_quality() call, or temporal statistics bleed across track boundaries
(and the 200-cap eventually displaces current-track data with stale values).

The reset was added in commit 6a8738a0 (#4221) but had no regression test; this
pins it so a revert is caught.
"""

import numpy as np
import pytest

from auralis.analysis.quality.quality_metrics import QualityMetrics

SR = 44100


def _high_crest_track() -> np.ndarray:
    """Quiet bed with one large transient → high crest factor."""
    rs = np.random.RandomState(1)
    audio = (rs.randn(SR, 2) * 0.02).astype(np.float32)
    audio[SR // 2] = 1.0
    return audio


def _low_crest_track() -> np.ndarray:
    """Square-ish full-scale signal → low crest factor."""
    rs = np.random.RandomState(2)
    audio = (np.sign(rs.randn(SR, 2)) * 0.5).astype(np.float32)
    return audio


def test_crest_history_does_not_bleed_across_tracks():
    qm = QualityMetrics(sample_rate=SR)

    qm.assess_quality(_high_crest_track())
    hist_a = qm.dynamic_range_analyzer.get_crest_factor_history()
    assert len(hist_a) == 1  # one analyze call per assess_quality

    qm.assess_quality(_low_crest_track())
    hist_b = qm.dynamic_range_analyzer.get_crest_factor_history()

    # Reset ⇒ only track B's crest remains. Without the reset this would be 2
    # ([crestA, crestB]) and would keep growing per track.
    assert len(hist_b) == 1
    assert hist_b[0] != hist_a[0]


def test_correlation_history_does_not_bleed_across_tracks():
    qm = QualityMetrics(sample_rate=SR)

    qm.assess_quality(_high_crest_track())
    len_a = len(qm.phase_analyzer.get_correlation_history())

    qm.assess_quality(_low_crest_track())
    len_b = len(qm.phase_analyzer.get_correlation_history())

    # History length after track B must not exceed its length after track A
    # (it is reset, not accumulated across tracks).
    assert len_b <= len_a


def test_reset_history_invoked_once_per_assess_quality(monkeypatch):
    qm = QualityMetrics(sample_rate=SR)
    calls = {'dr': 0, 'phase': 0}

    orig_dr = qm.dynamic_range_analyzer.reset_history
    orig_phase = qm.phase_analyzer.reset_history

    def dr_spy():
        calls['dr'] += 1
        return orig_dr()

    def phase_spy():
        calls['phase'] += 1
        return orig_phase()

    monkeypatch.setattr(qm.dynamic_range_analyzer, 'reset_history', dr_spy)
    monkeypatch.setattr(qm.phase_analyzer, 'reset_history', phase_spy)

    qm.assess_quality(_low_crest_track())

    assert calls['dr'] == 1
    assert calls['phase'] == 1
