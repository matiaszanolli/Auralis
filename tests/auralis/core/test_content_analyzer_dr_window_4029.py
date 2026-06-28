"""
ContentAnalyzer._estimate_dynamic_range window scaling (#4029).

The RMS window was hardcoded to 44100 samples (1 s only at 44.1 kHz); at 48/96
kHz it covered <1 s, biasing the dynamic-range estimate that feeds preset
selection. It now uses self.sample_rate so the window is always ~1 second.
"""

import numpy as np

from auralis.core.analysis.content_analyzer import ContentAnalyzer


def _analyzer(sr):
    return ContentAnalyzer(sample_rate=sr, use_ml_classification=False)


def test_constant_signal_has_low_dynamic_range_at_48k():
    sr = 48000
    audio = np.full(sr * 3, 0.3, dtype=np.float32)  # 3 s, constant amplitude
    dr = _analyzer(sr)._estimate_dynamic_range(audio)
    assert np.isfinite(dr)
    assert dr < 3.0  # near-constant -> small DR


def test_loud_quiet_signal_has_high_dynamic_range_at_48k():
    sr = 48000
    quiet = np.full(sr, 0.01, dtype=np.float32)
    loud = np.full(sr, 0.5, dtype=np.float32)
    audio = np.concatenate([quiet, loud, quiet, loud])  # alternating 1 s blocks
    dr = _analyzer(sr)._estimate_dynamic_range(audio)
    assert np.isfinite(dr)
    assert dr > 10.0  # 1 s windows resolve the loud/quiet contrast


def test_window_scales_with_sample_rate():
    # Same wall-clock signal at two rates should give comparable DR now that the
    # window is 1 s at both (it would diverge with a fixed 44100 window).
    quiet, loud = 0.01, 0.5
    drs = []
    for sr in (44100, 48000):
        audio = np.concatenate(
            [np.full(sr, quiet, np.float32), np.full(sr, loud, np.float32)] * 2
        )
        drs.append(_analyzer(sr)._estimate_dynamic_range(audio))
    assert abs(drs[0] - drs[1]) < 2.0  # within 2 dB across rates
