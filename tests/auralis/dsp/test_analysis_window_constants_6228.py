"""
Shared analysis window/hop constants (#6228).

The `frames_for_seconds(sr, 1024 / 44100)` time-anchored idiom was typed
inline at five sites in three files, each carrying the same comment, so
retuning the analysis window meant copying a magic ratio and the two
onset implementations could diverge. The ratios are now named once as
ANALYSIS_WINDOW_S / ANALYSIS_HOP_S beside frames_for_seconds.
"""

from __future__ import annotations

import numpy as np

from auralis.dsp.utils.spectral import (
    ANALYSIS_HOP_S,
    ANALYSIS_WINDOW_S,
    frames_for_seconds,
    tempo_estimate,  # onset path lives behind the tempo/onset analysis
)


def test_constants_reproduce_historical_sample_counts() -> None:
    # 1024/512 samples at the 44.1 kHz reference rate, exactly.
    assert frames_for_seconds(44100, ANALYSIS_WINDOW_S) == 1024
    assert frames_for_seconds(44100, ANALYSIS_HOP_S) == 512


def test_window_scales_with_sample_rate() -> None:
    # Same time duration at 48 kHz -> next power of two up (2048/1024),
    # not the bare 44.1 kHz literal.
    assert frames_for_seconds(48000, ANALYSIS_WINDOW_S) == 2048
    assert frames_for_seconds(48000, ANALYSIS_HOP_S) == 1024


def test_onset_window_unchanged_on_fixture() -> None:
    # The onset analysis (spectral flux inside tempo estimation) still
    # produces a finite tempo on a fixed fixture with the shared constants.
    t = np.arange(44100 * 2, dtype=np.float64) / 44100
    clicks = np.zeros(len(t))
    for beat in range(4):  # 2 Hz click train -> 120 BPM
        start = int(beat * 44100 / 2)
        clicks[start:start + 64] = np.hanning(64)
    assert np.isfinite(tempo_estimate(clicks.astype(np.float32), 44100))
