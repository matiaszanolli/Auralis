"""True peak is not inflated by the per-block resampler's edge steps (#6327).

measure_chunk oversampled each 400 ms block independently and resample_poly zero-pads block edges, so a sustained
tone non-zero at an edge overshot by ~1 dB and that was kept as the track's true peak. A -6.02 dBFS sine now reads
within 0.1 dB at every phase.
"""

import numpy as np
import pytest

from auralis.analysis.loudness_meter import LoudnessMeter

SR = 48000
AMPLITUDE = 0.5  # -6.02 dBFS


def _true_peak_dbfs(phase: float, seconds: float = 2.0) -> float:
    t = np.arange(int(SR * seconds)) / SR
    tone = AMPLITUDE * np.sin(2 * np.pi * 997.0 * t + phase)
    audio = np.column_stack([tone, tone]).astype(np.float64)
    meter = LoudnessMeter(sample_rate=SR)
    block = int(SR * 0.4)
    for start in range(0, len(audio), block):
        meter.measure_chunk(audio[start:start + block])
    return meter.finalize_measurement().true_peak_dbfs


@pytest.mark.parametrize("phase", [0.0, 0.7, 1.9, 3.1])
def test_a_sine_reads_its_true_peak_at_every_phase(phase):
    assert _true_peak_dbfs(phase) == pytest.approx(20 * np.log10(AMPLITUDE), abs=0.1)


def test_a_constant_block_is_not_inflated():
    meter = LoudnessMeter(sample_rate=SR)

    peak = meter._calculate_true_peak(np.full((int(SR * 0.4), 2), 0.5))

    assert peak == pytest.approx(20 * np.log10(0.5), abs=0.1)


def test_a_tiny_block_does_not_crash():
    meter = LoudnessMeter(sample_rate=SR)

    assert np.isfinite(meter._calculate_true_peak(np.array([[0.25, 0.25]])))
    assert meter._calculate_true_peak(np.zeros((1, 2))) == -np.inf
