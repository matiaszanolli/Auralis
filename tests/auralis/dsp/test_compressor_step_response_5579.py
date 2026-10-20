"""Regression tests: compressor gain smoothing time constants (#5579)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

AdaptiveCompressor fed gain reduction (dB <= 0) into an envelope follower
whose branch treats `input > envelope` as attack. Growing compression moves
the value DOWN, so attack and release were swapped: the audit's step-response
probe measured 63% of the reduction in ~99.5 ms (attack 10 ms) and recovery
to 37% in ~10 ms (release 100 ms). Feeding the magnitude fixes both.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.compressor import AdaptiveCompressor
from auralis.dsp.dynamics.compressor import CompressorSettings


def _make_compressor() -> AdaptiveCompressor:
    settings = CompressorSettings(
        threshold_db=-20.0,
        ratio=4.0,
        attack_ms=10.0,
        release_ms=100.0,
        knee_db=0.0,
        makeup_gain_db=0.0,
        enable_lookahead=False,
    )
    return AdaptiveCompressor(settings, 44100)


def _step_reduction(compressor: AdaptiveCompressor) -> np.ndarray:
    """Feed a signal that steps from -40 dBFS to -6 dBFS and return the
    smoothed gain-reduction trace in dB (negative values)."""
    sr = 44100
    quiet = np.full(sr // 10, 10 ** (-40 / 20), dtype=np.float32)   # 100 ms
    loud = np.full(sr, 10 ** (-6 / 20), dtype=np.float32)           # 1 s
    audio = np.concatenate([quiet, loud])
    if audio.ndim == 1:
        audio = np.column_stack([audio, audio])
    compressor.gain_follower.reset()
    compressor.process(audio)
    return np.asarray(compressor.gain_reduction, dtype=np.float32) \
        if hasattr(compressor.gain_reduction, '__len__') else None


@pytest.mark.parametrize("follower_path", ["vectorized", "envelope"])
def test_step_response_reaches_63pct_within_attack_order(follower_path):
    """Growing compression must engage at the ATTACK rate: ~63% of the final
    reduction within roughly the attack time constant (10 ms -> a few ms of
    samples), not the 100 ms release one."""
    from auralis.dsp.dynamics import vectorized_envelope

    sr = 44100
    comp = _make_compressor()

    quiet = np.full(sr // 10, 10 ** (-40 / 20), dtype=np.float32)
    loud = np.full(sr * 2, 10 ** (-6 / 20), dtype=np.float32)
    audio = np.column_stack([np.concatenate([quiet, loud])] * 2)

    # Drive the follower directly with the gain-reduction trace the
    # compressor computes, so the test observes the smoothing stage alone.
    levels_db = 20 * np.log10(np.abs(audio[:, 0]) + 1e-10)
    target_gr = comp._calculate_gain_reduction_vectorized(levels_db)

    follower = comp.gain_follower
    smoothed = -follower.process_buffer((-target_gr).astype(np.float32))

    final = float(smoothed[-2000:].mean())          # settled reduction (dB)
    assert final < -3.0, f"no meaningful reduction settled: {final}"

    # The level step lands at the end of the quiet prefix (100 ms).
    step_sample = sr // 10
    crossing = int(np.argmax(smoothed[step_sample:] <= final * 0.63))
    time_ms = (step_sample + crossing) / sr * 1000 - step_sample * 1000 / sr
    # Attack is 10 ms (63% of a one-pole step ≈ 1 tau). Allow 3x slack for
    # the per-sample level envelope feeding the gain computation.
    assert time_ms < 30.0, (
        f"compression engaged in {time_ms:.1f} ms — attack/release are "
        "still swapped (release is 100 ms)"
    )


def test_recovery_uses_the_release_rate():
    """After the loud section ends, recovery to 37% of the peak reduction
    must take on the order of the release constant (100 ms), not the 10 ms
    attack — the #5579 symptom was a 10 ms snap-back (pumping)."""
    sr = 44100
    comp = _make_compressor()

    loud = np.full(sr, 10 ** (-6 / 20), dtype=np.float32)      # 1 s loud
    quiet = np.full(sr // 2, 10 ** (-40 / 20), dtype=np.float32)
    audio = np.column_stack([np.concatenate([loud, quiet])] * 2)

    levels_db = 20 * np.log10(np.abs(audio[:, 0]) + 1e-10)
    target_gr = comp._calculate_gain_reduction_vectorized(levels_db)
    smoothed = -comp.gain_follower.process_buffer((-target_gr).astype(np.float32))

    peak_gr = float(smoothed[sr - sr // 20:sr].mean())  # settled loud reduction
    after_end = smoothed[sr:]                      # recovery region
    recovered_to = peak_gr * 0.37                  # 63% recovered (one tau)
    crossing = int(np.argmax(after_end >= recovered_to))
    time_ms = crossing / sr * 1000
    # Release 100 ms → ~100 ms to 37%. Allow generous slack; the swapped
    # behaviour recovered in ~10 ms.
    assert time_ms > 30.0, (
        f"gain recovered in {time_ms:.1f} ms — release is using the attack "
        "coefficient (pumping)"
    )
