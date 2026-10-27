"""
Regression: the cross-dimensional guards measure the whole buffer, not its first 2 s (#5723)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_compute_3band_energy` and `_compute_phase_correlation` truncated to
`sample_rate * 2` samples from the START of the buffer (and the 3-band split used
channel 0 only). For a backend chunk past the first, that window is leading
context that is rendered and then thrown away.
"""

import numpy as np
import pytest

from auralis.core.processing import stage_snapshot as ss
from auralis.core.processing.stage_snapshot import (
    PipelineJournal,
    _analysis_windows,
    _compute_3band_energy,
    _compute_phase_correlation,
)

SR = 44100


def _tone(freq: float, seconds: float, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    return amp * np.sin(2 * np.pi * freq * t)


def _buffer(quiet_head_s: float, tail: np.ndarray) -> np.ndarray:
    return np.concatenate([np.zeros(int(SR * quiet_head_s)), tail])


class TestWindows:
    def test_short_buffer_is_measured_whole(self):
        audio = np.zeros((SR, 2))
        windows = _analysis_windows(audio, SR)
        assert len(windows) == 1 and windows[0] is audio

    def test_long_buffer_is_sampled_across_its_whole_length_within_the_budget(self):
        audio = np.arange(15 * SR, dtype=float)
        windows = _analysis_windows(audio, SR)

        assert sum(len(w) for w in windows) <= 2 * SR
        assert windows[0][0] == 0
        assert windows[-1][-1] == len(audio) - 1  # reaches the very end

    def test_windows_are_evenly_spaced(self):
        audio = np.arange(15 * SR, dtype=float)
        starts = [int(w[0]) for w in _analysis_windows(audio, SR)]
        gaps = np.diff(starts)
        assert gaps.max() - gaps.min() <= 1


class TestThreeBand:
    def test_quiet_head_followed_by_bass_heavy_body_reads_bass(self):
        """The old head-only version saw only the silent first 5 s."""
        audio = _buffer(5.0, _tone(80.0, 10.0))

        bass, mid, high = _compute_3band_energy(audio, SR)

        assert bass > 0.9 and mid < 0.1 and high < 0.1

    def test_high_content_only_in_the_tail_is_seen(self):
        audio = _buffer(6.0, _tone(8000.0, 9.0))

        _, _, high = _compute_3band_energy(audio, SR)

        assert high > 0.9

    def test_stereo_split_uses_both_channels(self):
        left = _tone(80.0, 4.0)
        right = _tone(8000.0, 4.0)
        bass, _, high = _compute_3band_energy(np.stack([left, right], axis=1), SR)

        assert 0.3 < bass < 0.7 and 0.3 < high < 0.7  # not channel 0's 100 % bass

    def test_silence_is_an_even_split(self):
        assert _compute_3band_energy(np.zeros(20 * SR), SR) == (0.33, 0.34, 0.33)

    def test_fractions_sum_to_one(self):
        rng = np.random.default_rng(0)
        assert sum(_compute_3band_energy(rng.standard_normal((15 * SR, 2)), SR)) == pytest.approx(1.0)

    def test_kept_audio_counts_in_proportion_to_its_share_of_the_buffer(self):
        """5 s of 8 kHz context in front of 10 s of 100 Hz body. The old head-only
        measurement read 0 % bass (it saw only the context); the whole-buffer
        measurement gives the body its two-thirds share, so two renderings that
        differ only in their leading context stay close."""
        body = _tone(100.0, 10.0)
        quiet_context = _buffer(5.0, body)
        loud_context = np.concatenate([_tone(8000.0, 5.0), body])

        bass_quiet, _, _ = _compute_3band_energy(quiet_context, SR)
        bass_loud, _, _ = _compute_3band_energy(loud_context, SR)

        assert bass_quiet == pytest.approx(1.0, abs=0.05)
        assert bass_loud == pytest.approx(10 / 15, abs=0.1)


class TestPhaseCorrelation:
    def test_wide_second_half_is_reflected(self):
        n = 15 * SR
        left = _tone(220.0, 15.0)
        right = left.copy()
        right[n // 2:] = -right[n // 2:]  # anti-phase for the second half
        audio = np.stack([left, right], axis=1)

        corr = _compute_phase_correlation(audio, SR)

        assert corr is not None and corr < 0.3  # old head-only: +1.0

    def test_mono_stays_one(self):
        mono = _tone(220.0, 15.0)
        assert _compute_phase_correlation(np.stack([mono, mono], axis=1), SR) == pytest.approx(1.0)

    def test_non_stereo_is_none(self):
        assert _compute_phase_correlation(_tone(220.0, 1.0), SR) is None


class TestJournalUsesTheSameWindow:
    def test_snapshot_agrees_with_the_guard_helpers(self):
        audio = np.stack([_buffer(5.0, _tone(100.0, 10.0))] * 2, axis=1)

        snap = PipelineJournal(SR).snapshot(audio, "t")

        assert (snap.bass_energy_pct, snap.mid_energy_pct, snap.high_energy_pct) == pytest.approx(
            _compute_3band_energy(audio, SR)
        )
        assert snap.phase_correlation == _compute_phase_correlation(audio, SR)


def test_measurement_cost_stays_bounded_whatever_the_buffer_length():
    """Samples measured are capped at the old 2 s budget for any buffer length."""
    budget = 2 * SR
    for seconds in (3, 15, 600):
        windows = _analysis_windows(np.zeros(seconds * SR), SR)
        assert sum(len(w) for w in windows) <= budget
