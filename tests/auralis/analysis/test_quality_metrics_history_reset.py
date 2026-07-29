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


# ---------------------------------------------------------------------------
# #4539: the spectrum analyzer was the sibling #4221 missed
# ---------------------------------------------------------------------------

def _bright_loud_track() -> np.ndarray:
    """High-frequency-dominant, loud → high spectral centroid."""
    t = np.arange(SR * 2) / SR
    mono = 0.8 * np.sin(2 * np.pi * 8000 * t)
    return np.column_stack([mono, mono]).astype(np.float32)


def _dark_quiet_track() -> np.ndarray:
    """Low-frequency-dominant, quiet → low spectral centroid."""
    t = np.arange(SR * 2) / SR
    mono = 0.05 * np.sin(2 * np.pi * 100 * t)
    return np.column_stack([mono, mono]).astype(np.float32)


_SPECTRAL_KEYS = ("spectral_centroid", "spectral_rolloff", "peak_frequency")


def test_spectral_metrics_do_not_bleed_across_assess_quality_calls():
    """A prior track's trailing smoothed spectrum must not colour the next.

    SpectrumAnalyzer.smoothing_buffer is read and overwritten on every chunk
    and feeds spectral_centroid / spectral_rolloff / peak_frequency directly,
    so a reused QualityMetrics measured every track through the previous
    track's residue (#4539).
    """
    contaminated = QualityMetrics(sample_rate=SR)
    contaminated.assess_quality(_bright_loud_track())
    after_bright = contaminated.spectrum_analyzer.analyze_file(
        _dark_quiet_track()[:, 0]
    )

    fresh = QualityMetrics(sample_rate=SR)
    clean = fresh.spectrum_analyzer.analyze_file(_dark_quiet_track()[:, 0])

    for key in _SPECTRAL_KEYS:
        assert after_bright[key] == pytest.approx(clean[key], rel=1e-6), (
            f"{key} differs depending on what was analyzed before it"
        )


def test_frequency_response_score_is_order_independent():
    """The full public metric, not just the raw spectrum."""
    qm = QualityMetrics(sample_rate=SR)
    qm.assess_quality(_bright_loud_track())
    dark_after_bright = qm.assess_quality(_dark_quiet_track())

    dark_alone = QualityMetrics(sample_rate=SR).assess_quality(_dark_quiet_track())

    assert dark_after_bright.frequency_response_score == pytest.approx(
        dark_alone.frequency_response_score, rel=1e-6
    )


def test_smoothing_buffer_is_cleared_before_analysis():
    """Direct guard on the reset itself."""
    qm = QualityMetrics(sample_rate=SR)
    qm.assess_quality(_bright_loud_track())
    assert qm.spectrum_analyzer.smoothing_buffer is not None  # state accrued

    qm._reset_analyzers()
    assert qm.spectrum_analyzer.smoothing_buffer is None


def test_compare_quality_is_symmetric():
    """compare_quality() runs two assess_quality() calls on one instance, so
    the second argument used to be measured through the first's residue."""
    qm_ab = QualityMetrics(sample_rate=SR)
    ab = qm_ab.compare_quality(_bright_loud_track(), _dark_quiet_track())

    qm_ba = QualityMetrics(sample_rate=SR)
    ba = qm_ba.compare_quality(_dark_quiet_track(), _bright_loud_track())

    # Each track's own measured score must not depend on the ordering: the
    # bright track is audio1 in one call and audio2 in the other.
    assert ab["sub_scores"]["audio1"]["frequency_response"] == pytest.approx(
        ba["sub_scores"]["audio2"]["frequency_response"], rel=1e-6
    )
    assert ab["sub_scores"]["audio2"]["frequency_response"] == pytest.approx(
        ba["sub_scores"]["audio1"]["frequency_response"], rel=1e-6
    )
    # ...and therefore the reported delta is exactly antisymmetric.
    assert ab["difference"] == pytest.approx(-ba["difference"], rel=1e-6)


@pytest.mark.parametrize(
    "attr,probe",
    [
        ("spectrum_analyzer", lambda a: a.smoothing_buffer is None),
        ("phase_analyzer", lambda a: len(a.get_correlation_history()) == 0),
        ("dynamic_range_analyzer", lambda a: len(a.get_crest_factor_history()) == 0),
    ],
)
def test_every_stateful_analyzer_is_reset(attr, probe):
    """Parametrized so adding a stateful member without resetting it fails here
    rather than being discovered a release later, which is how #4539 happened
    to #4221."""
    qm = QualityMetrics(sample_rate=SR)
    qm.assess_quality(_bright_loud_track())
    qm._reset_analyzers()
    assert probe(getattr(qm, attr)), f"{attr} was not reset"


def test_reset_analyzers_covers_every_stateful_member():
    """CONSISTENCY: the reset list must not drift from __init__'s members.

    Asserts by construction rather than by eyeball — any analyzer object held
    on the instance that exposes a reset hook must be named in
    _reset_analyzers' source.
    """
    import inspect

    source = inspect.getsource(QualityMetrics._reset_analyzers)
    qm = QualityMetrics(sample_rate=SR)
    for name, member in vars(qm).items():
        resettable = any(
            hasattr(member, hook)
            for hook in ("reset", "reset_history", "reset_smoothing")
        )
        if resettable:
            assert name in source, (
                f"self.{name} exposes a reset hook but is not reset in "
                f"_reset_analyzers() — this is exactly the #4539 omission"
            )
