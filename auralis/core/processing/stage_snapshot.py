"""
Stage Snapshot & Pipeline Journal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Lightweight inter-stage measurement bus for cross-dimensional analysis.
Captures the multi-dimensional state of audio after each processing stage
without adding significant latency (~2ms per snapshot).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import weakref
from auralis.dsp.utils.conversion import SILENCE_STD_THRESHOLD
from dataclasses import dataclass

import numpy as np
from scipy.fft import rfft, rfftfreq

from .base import FullAudioMeasurement, StereoWidthProcessor
from ...dsp.utils.adaptive import calculate_loudness_units
from ...dsp.utils.audio_info import to_mono
from ...dsp.utils.stereo import stereo_width_analysis
from ...utils.logging import debug


@dataclass(frozen=True)
class StageSnapshot:
    """Lightweight multi-dimensional measurement at a single pipeline point."""
    stage_name: str
    peak_db: float
    rms_db: float
    crest_db: float
    lufs: float | None
    # 3-band energy split (fraction of total, sums to ~1.0)
    bass_energy_pct: float   # 20-250 Hz
    mid_energy_pct: float    # 250-4000 Hz
    high_energy_pct: float   # 4000+ Hz
    # Stereo (None for mono)
    stereo_width: float | None
    phase_correlation: float | None


# The guards used to measure the first 2 s of channel 0, which for a backend
# chunk past the first is leading context that is rendered and then discarded
# (chunk_boundaries.emitted_chunk_start), so the tilt and phase decisions that
# are applied to the whole buffer were made on audio nobody hears (#5723). They
# now measure 8 windows of 0.25 s spread evenly over the whole buffer: the same
# 2 s budget, but representative of it.
_ANALYSIS_WINDOW_S = 0.25
_ANALYSIS_WINDOWS = 8


def _analysis_windows(audio: np.ndarray, sample_rate: int) -> list[np.ndarray]:
    """Evenly spaced windows over the whole buffer, <= 2 s of audio in total.

    A buffer that already fits the budget is returned whole. Windows are kept
    separate (not concatenated) so a spectral measurement never sees the join.
    """
    window = int(sample_rate * _ANALYSIS_WINDOW_S)
    if len(audio) <= window * _ANALYSIS_WINDOWS:
        return [audio]
    starts = np.linspace(0, len(audio) - window, _ANALYSIS_WINDOWS).astype(int)
    return [audio[start:start + window] for start in starts]


def _compute_3band_energy(audio: np.ndarray, sample_rate: int) -> tuple[float, float, float]:
    """3-band energy split (bass/mid/high) from FFTs of windows spread over the buffer.

    Measures the mid (L+R)/2 of stereo input, so a channel-0-only quirk cannot
    steer the tilt guard. Power is summed across windows before taking ratios.
    """
    bass = mid = high = 0.0
    for chunk in _analysis_windows(audio, sample_rate):
        signal = to_mono(chunk)
        power = np.abs(rfft(signal * np.hanning(len(signal)))) ** 2
        freqs = rfftfreq(len(signal), d=1.0 / sample_rate)
        bass += power[freqs < 250].sum()
        mid += power[(freqs >= 250) & (freqs < 4000)].sum()
        high += power[freqs >= 4000].sum()

    total = bass + mid + high
    if total < 1e-12:
        return 0.33, 0.34, 0.33  # silence — equal distribution
    return float(bass / total), float(mid / total), float(high / total)


def _compute_phase_correlation(audio: np.ndarray, sample_rate: int) -> float | None:
    """Phase correlation between L/R over windows spread across the buffer.

    sample_rate is required (#4622) — it sets the window size and spacing, so a
    missing/wrong value silently measures the wrong amount of audio.
    """
    if not StereoWidthProcessor.validate_stereo(audio):
        return None
    windows = _analysis_windows(audio, sample_rate)
    left = np.concatenate([w[:, 0] for w in windows])
    right = np.concatenate([w[:, 1] for w in windows])
    # #6230: the same named threshold dsp/utils/stereo.py's guard uses.
    if np.std(left) < SILENCE_STD_THRESHOLD or np.std(right) < SILENCE_STD_THRESHOLD:
        return 1.0  # mono/silence → perfect correlation
    return float(np.corrcoef(left, right)[0, 1])


class PipelineJournal:
    """Accumulates StageSnapshots across the processing pipeline.

    Created per-call inside ``ContinuousMode.process()`` — no persistent state,
    no thread-safety concern.
    """

    def __init__(self, sample_rate: int) -> None:
        self.sample_rate = sample_rate
        self._snapshots: list[StageSnapshot] = []
        # The latest snapshot's buffer and LUFS. Held weakly: a strong reference
        # would keep a whole-track copy alive through every later stage (#6717).
        self._latest_lufs: tuple[weakref.ref[np.ndarray], float] | None = None

    def snapshot(self, audio: np.ndarray, stage_name: str, lufs: float | None = None) -> StageSnapshot:
        """Capture a snapshot (~2ms for 15-second stereo chunk).

        ``lufs`` is ``audio``'s K-weighted loudness when the caller already has it.
        A stage that returns its input unchanged hands back the very buffer the
        latest reading measured, which is then reused rather than re-metered.
        """
        if lufs is None and self._latest_lufs is not None and self._latest_lufs[0]() is audio:
            lufs = self._latest_lufs[1]
        m = FullAudioMeasurement(audio, self.sample_rate, label=stage_name, lufs=lufs)
        if m.lufs is not None:
            self._latest_lufs = (weakref.ref(audio), m.lufs)
        bass, mid, high = _compute_3band_energy(audio, self.sample_rate)

        is_stereo = StereoWidthProcessor.validate_stereo(audio)
        width = stereo_width_analysis(audio) if is_stereo else None
        phase = _compute_phase_correlation(audio, self.sample_rate) if is_stereo else None

        snap = StageSnapshot(
            stage_name=stage_name,
            peak_db=m.peak_db,
            rms_db=m.rms_db,
            crest_db=m.crest,
            lufs=m.lufs,
            bass_energy_pct=bass,
            mid_energy_pct=mid,
            high_energy_pct=high,
            stereo_width=width,
            phase_correlation=phase,
        )
        self._snapshots.append(snap)
        debug(f"[Journal] {stage_name}: peak={snap.peak_db:.1f}dB rms={snap.rms_db:.1f}dB "
              f"crest={snap.crest_db:.1f}dB bass={bass:.0%} mid={mid:.0%} high={high:.0%}"
              + (f" lufs={snap.lufs:.1f}" if snap.lufs is not None else "")
              + (f" width={width:.2f} phase={phase:.2f}" if is_stereo else ""))
        return snap

    def moved(self, old: np.ndarray, new: np.ndarray) -> None:
        """``old``'s contents are being copied into ``new`` (the stage loop's working buffer, #6717).

        A reading of ``old`` now belongs to ``new``; a reading of ``new`` itself is
        dropped, since its contents are about to change.
        """
        if self._latest_lufs is None:
            return
        held = self._latest_lufs[0]()
        if held is old:
            self._latest_lufs = (weakref.ref(new), self._latest_lufs[1])
        elif held is new:
            self._latest_lufs = None

    def lufs(self, audio: np.ndarray) -> float:
        """K-weighted loudness of ``audio``, reusing the latest snapshot's reading.

        A stage measures the buffer a snapshot has just measured (the EQ guard's
        before and after, the chunk normaliser's input), and K-weighting a whole
        track costs as much as a DSP stage. The match is by identity, not content:
        pipeline buffers are never modified in place, every stage returns a new array.
        """
        if self._latest_lufs is not None and self._latest_lufs[0]() is audio:
            return self._latest_lufs[1]
        return calculate_loudness_units(audio, self.sample_rate)

    def get(self, stage_name: str) -> StageSnapshot | None:
        """Retrieve a snapshot by stage name."""
        for s in self._snapshots:
            if s.stage_name == stage_name:
                return s
        return None

    @property
    def snapshots(self) -> list[StageSnapshot]:
        return list(self._snapshots)
