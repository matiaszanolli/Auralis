"""
Regression test for #3466 — LoudnessMeter integrated LUFS must average
over the entire measurement, not just the bounded short-term buffer.

Prior bug: `measure_chunk()` appended to `block_buffer` and truncated
with `pop(0)` after `short_term_blocks=30`. `finalize_measurement()`
then read the (truncated) buffer for ITU-R BS.1770 integrated LUFS —
the result reflected only the most recent ~30 blocks, biasing the
integrated value toward the track's tail.

Fix: maintain a separate unbounded `integrated_buffer` populated alongside
`block_buffer`; `finalize_measurement` reads from `integrated_buffer`.
"""

from __future__ import annotations

import numpy as np
import pytest

from auralis.analysis.loudness_meter import LoudnessMeter


SR = 44100


def _stereo_sine(amplitude: float, duration_s: float, freq: float = 1000.0) -> np.ndarray:
    """Generate a stereo sine at the given linear amplitude."""
    t = np.arange(int(duration_s * SR)) / SR
    mono = amplitude * np.sin(2 * np.pi * freq * t)
    return np.column_stack([mono, mono]).astype(np.float32)


def _feed(meter: LoudnessMeter, audio: np.ndarray) -> None:
    """Feed audio in block-sized chunks (matching the fingerprint analyzer)."""
    block_size = meter.block_size
    for start in range(0, len(audio), block_size):
        chunk = audio[start:start + block_size]
        if len(chunk) >= block_size:
            meter.measure_chunk(chunk)


def test_integrated_lufs_reflects_full_signal_not_tail():
    """A long quiet section followed by a short loud section must NOT
    produce an integrated LUFS dominated by the loud tail."""
    meter = LoudnessMeter(SR)

    # ~20 seconds of quiet (-30 dBFS sine) — produces ~50 blocks at the
    # 400 ms block size, well past short_term_blocks=30. With the bug,
    # those quiet blocks fall out of the buffer before finalize.
    quiet = _stereo_sine(amplitude=10 ** (-30 / 20), duration_s=20.0)

    # ~2 seconds of loud (-10 dBFS sine) — fewer blocks.
    loud = _stereo_sine(amplitude=10 ** (-10 / 20), duration_s=2.0)

    audio = np.concatenate([quiet, loud], axis=0)
    _feed(meter, audio)

    measurement = meter.finalize_measurement()

    # Pre-fix: the bounded buffer holds only the last ~30 blocks (the loud
    # tail), so integrated LUFS ≈ -10 dB.
    # Post-fix: the integrated buffer holds the full 22 s. ITU-R BS.1770
    # relative gating (ungated_LUFS − 10 LU) drops the quietest blocks,
    # so the value lands ~between quiet (-30) and loud (-10), around -20.
    # The discriminating threshold is well above -15 (clearly bug) vs.
    # well below -15 (fix working).
    assert measurement.integrated_lufs < -15.0, (
        f"Integrated LUFS should reflect the full signal (~-20 dB after "
        f"BS.1770 relative gating), got {measurement.integrated_lufs:.1f} dB. "
        f"If this is close to -10, the bug (tail-only integrated) is back."
    )


def test_integrated_lufs_uses_all_blocks_after_30():
    """Direct check: after feeding > short_term_blocks chunks, the
    integrated_buffer retains every block."""
    meter = LoudnessMeter(SR)

    # 60 blocks worth of sine at -20 dBFS (twice short_term_blocks)
    duration = 60 * (meter.block_size / SR)
    audio = _stereo_sine(amplitude=10 ** (-20 / 20), duration_s=duration)
    _feed(meter, audio)

    # block_buffer must be truncated (bounded for short-term window)
    assert len(meter.block_buffer) == meter.short_term_blocks
    # integrated_buffer must be unbounded
    assert len(meter.integrated_buffer) >= 60

    # measurement_duration must reflect the FULL signal as actual seconds
    # of audio fed (#3307), not call count × hardcoded 0.1 s.
    measurement = meter.finalize_measurement()
    expected_seconds = (len(meter.integrated_buffer) * meter.block_size) / SR
    assert measurement.measurement_duration == pytest.approx(expected_seconds)
    assert measurement.measurement_duration >= 24.0  # 60 blocks × 0.4 s


def test_reset_clears_both_buffers():
    """`reset()` must clear the integrated buffer too, or a second
    measurement leaks blocks from the first."""
    meter = LoudnessMeter(SR)
    _feed(meter, _stereo_sine(amplitude=10 ** (-20 / 20), duration_s=3.0))

    assert len(meter.integrated_buffer) > 0
    meter.reset()

    assert meter.block_buffer == []
    assert meter.integrated_buffer == []


def test_short_term_window_still_bounded():
    """The fix must not regress the short-term/momentary windows —
    `block_buffer` is still truncated to `short_term_blocks`."""
    meter = LoudnessMeter(SR)

    duration = 50 * (meter.block_size / SR)
    _feed(meter, _stereo_sine(amplitude=10 ** (-18 / 20), duration_s=duration))

    assert len(meter.block_buffer) == meter.short_term_blocks


# ---------------------------------------------------------------------------
# #3307 — measurement_duration must reflect actual sample count
# ---------------------------------------------------------------------------

def test_measurement_duration_matches_audio_for_400ms_chunks():
    """Feeding 400 ms blocks (fingerprint analyzer path) must report
    duration equal to call_count × 0.4 s, not × 0.1 s."""
    meter = LoudnessMeter(SR)
    audio = _stereo_sine(amplitude=10 ** (-20 / 20), duration_s=10.0)
    _feed(meter, audio)

    measurement = meter.finalize_measurement()
    # Only complete 400 ms blocks are fed by _feed; expected duration is
    # n_blocks * block_size / SR. For a 10 s clip with 400 ms blocks,
    # 25 blocks fit exactly, so duration is exactly 10 s.
    expected = (len(meter.integrated_buffer) * meter.block_size) / SR
    assert measurement.measurement_duration == pytest.approx(expected, abs=1e-3)
    assert measurement.measurement_duration == pytest.approx(10.0, abs=1e-3)


def test_measurement_duration_matches_audio_for_arbitrary_chunks():
    """Acceptance criterion (#3307): measurement_duration must match the
    actual audio duration passed to the meter within ±1 ms, regardless of
    block size. Verifies the fix is correct for non-standard chunk sizes
    (here: 1024-sample chunks, ~23.2 ms each — unrelated to the assumed
    100 ms hop or 400 ms block)."""
    meter = LoudnessMeter(SR)
    duration_s = 5.0
    audio = _stereo_sine(amplitude=10 ** (-20 / 20), duration_s=duration_s)

    chunk = 1024
    fed = 0
    for start in range(0, len(audio), chunk):
        block = audio[start:start + chunk]
        meter.measure_chunk(block)
        fed += len(block)

    measurement = meter.finalize_measurement()
    expected_duration = fed / SR
    assert measurement.measurement_duration == pytest.approx(expected_duration, abs=1e-3)
    # Audio length equals fed length (no truncation), so duration ≈ 5.0 s.
    assert measurement.measurement_duration == pytest.approx(duration_s, abs=1e-3)


def test_reset_clears_total_samples():
    """A second measurement after reset must not inherit the prior count."""
    meter = LoudnessMeter(SR)
    _feed(meter, _stereo_sine(amplitude=10 ** (-20 / 20), duration_s=3.0))
    assert meter.finalize_measurement().measurement_duration > 0

    meter.reset()
    assert meter._total_samples == 0
    # Empty meter reports 0.0 (the early-return branch).
    assert meter.finalize_measurement().measurement_duration == 0.0

