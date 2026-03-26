"""
Stage Snapshot & Pipeline Journal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Lightweight inter-stage measurement bus for cross-dimensional analysis.
Captures the multi-dimensional state of audio after each processing stage
without adding significant latency (~2ms per snapshot).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass

import numpy as np
from scipy.fft import rfft, rfftfreq

from .base import FullAudioMeasurement
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


def _compute_3band_energy(audio: np.ndarray, sample_rate: int) -> tuple[float, float, float]:
    """Fast 3-band energy split using a single FFT on the first channel."""
    # Use first channel (or mono) for spectral analysis
    signal = audio[:, 0] if audio.ndim == 2 else audio
    # Limit to 2 seconds for speed on long chunks
    max_samples = min(len(signal), sample_rate * 2)
    signal = signal[:max_samples]

    spectrum = np.abs(rfft(signal))
    freqs = rfftfreq(len(signal), d=1.0 / sample_rate)

    power = spectrum ** 2
    total = power.sum()
    if total < 1e-12:
        return 0.33, 0.34, 0.33  # silence — equal distribution

    bass = power[freqs < 250].sum() / total
    mid = power[(freqs >= 250) & (freqs < 4000)].sum() / total
    high = power[freqs >= 4000].sum() / total
    return float(bass), float(mid), float(high)


def _compute_phase_correlation(audio: np.ndarray) -> float | None:
    """Fast phase correlation between L/R channels."""
    if audio.ndim != 2 or audio.shape[1] != 2:
        return None
    left, right = audio[:, 0], audio[:, 1]
    if np.std(left) < 1e-9 or np.std(right) < 1e-9:
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

    def snapshot(self, audio: np.ndarray, stage_name: str) -> StageSnapshot:
        """Capture a snapshot (~2ms for 15-second stereo chunk)."""
        m = FullAudioMeasurement(audio, self.sample_rate, label=stage_name)
        bass, mid, high = _compute_3band_energy(audio, self.sample_rate)

        is_stereo = audio.ndim == 2 and audio.shape[1] == 2
        width = stereo_width_analysis(audio) if is_stereo else None
        phase = _compute_phase_correlation(audio) if is_stereo else None

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
              + (f" width={width:.2f} phase={phase:.2f}" if is_stereo else ""))
        return snap

    def get(self, stage_name: str) -> StageSnapshot | None:
        """Retrieve a snapshot by stage name."""
        for s in self._snapshots:
            if s.stage_name == stage_name:
                return s
        return None

    @property
    def snapshots(self) -> list[StageSnapshot]:
        return list(self._snapshots)

    def get_delta(self, stage_a: str, stage_b: str) -> dict[str, float]:
        """Compute the difference between two snapshots."""
        a, b = self.get(stage_a), self.get(stage_b)
        if a is None or b is None:
            return {}
        delta: dict[str, float] = {
            'peak_db': b.peak_db - a.peak_db,
            'rms_db': b.rms_db - a.rms_db,
            'crest_db': b.crest_db - a.crest_db,
            'bass_energy_pct': b.bass_energy_pct - a.bass_energy_pct,
            'mid_energy_pct': b.mid_energy_pct - a.mid_energy_pct,
            'high_energy_pct': b.high_energy_pct - a.high_energy_pct,
        }
        if a.lufs is not None and b.lufs is not None:
            delta['lufs'] = b.lufs - a.lufs
        if a.stereo_width is not None and b.stereo_width is not None:
            delta['stereo_width'] = b.stereo_width - a.stereo_width
        if a.phase_correlation is not None and b.phase_correlation is not None:
            delta['phase_correlation'] = b.phase_correlation - a.phase_correlation
        return delta
