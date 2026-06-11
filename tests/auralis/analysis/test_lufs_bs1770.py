"""BS.1770-4 K-weighting coefficient regression tests (#4213).

Verifies that LoudnessMeter uses the correct ITU-R BS.1770-4 parameters:
  - High-shelf at 1681.974 Hz +3.999843 dB  (was 1500 Hz +4 dB)
  - 2nd-order HP at 38.135 Hz               (was 1st-order 40 Hz)
"""
import numpy as np
from scipy import signal as scipy_signal

SR = 48000  # Use 48 kHz — BS.1770-4 reference sample rate


def _make_meter(sr: int = SR):
    from auralis.analysis.loudness_meter import LoudnessMeter
    return LoudnessMeter(sample_rate=sr)


def _sine(freq: float, rms: float, duration: float, sr: int = SR) -> np.ndarray:
    """Generate a sine wave at a specific RMS level."""
    n = int(duration * sr)
    t = np.arange(n) / sr
    amplitude = rms * np.sqrt(2)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float64)


def _feed_and_finalize(meter, audio: np.ndarray, block_size: int = 19200):
    """Feed audio in blocks and return finalized LUFSMeasurement."""
    for start in range(0, len(audio), block_size):
        meter.measure_chunk(audio[start:start + block_size])
    return meter.finalize_measurement()


class TestKWeightingCoefficients:
    def test_hp_is_second_order(self):
        """HP must be 2nd-order (3 coefficients) per BS.1770-4."""
        m = _make_meter()
        # 2nd-order Butterworth returns (b, a) each of length 3
        assert len(m.pre_filter_b) == 3
        assert len(m.pre_filter_a) == 3

    def test_hp_corner_near_38hz(self):
        """HP -3 dB point must be near 38 Hz, not 40 Hz."""
        m = _make_meter()
        freqs, h = scipy_signal.freqz(m.pre_filter_b, m.pre_filter_a, worN=4096, fs=SR)
        mag = 20 * np.log10(np.abs(h) + 1e-12)
        # At 38 Hz should be close to -3 dB; at 40 Hz should be above -3 dB
        idx_38 = np.argmin(np.abs(freqs - 38.0))
        idx_40 = np.argmin(np.abs(freqs - 40.0))
        assert -5.0 < mag[idx_38] < -1.0, f"Expected HP near -3 dB at 38 Hz, got {mag[idx_38]:.2f} dB"
        # At 40 Hz (old cutoff), response should now be above -3 dB (i.e. not the edge)
        assert mag[idx_40] > -3.0, f"HP should pass 40 Hz above -3 dB, got {mag[idx_40]:.2f} dB"

    def test_shelf_gain_near_zero_at_1khz(self):
        """RLB shelf must be ~0 dB at 1 kHz (below the shelf frequency)."""
        m = _make_meter()
        freqs, h = scipy_signal.freqz(m.rlb_filter_b, m.rlb_filter_a, worN=8192, fs=SR)
        mag = 20 * np.log10(np.abs(h) + 1e-12)
        idx_1k = np.argmin(np.abs(freqs - 1000.0))
        assert -1.0 < mag[idx_1k] < 1.0, f"Shelf at 1kHz must be ~0 dB, got {mag[idx_1k]:.2f} dB"

    def test_shelf_gain_near_4db_at_high_freq(self):
        """RLB shelf must approach +3.999843 dB at high frequencies."""
        m = _make_meter()
        freqs, h = scipy_signal.freqz(m.rlb_filter_b, m.rlb_filter_a, worN=8192, fs=SR)
        mag = 20 * np.log10(np.abs(h) + 1e-12)
        idx_20k = np.argmin(np.abs(freqs - 20000.0))
        assert 3.0 < mag[idx_20k] < 5.0, f"Shelf at 20kHz must be ~+4 dB, got {mag[idx_20k]:.2f} dB"

    def test_shelf_midpoint_near_1681hz(self):
        """Shelf midpoint (-3 dB from passband to shelf) must be near 1681.974 Hz."""
        m = _make_meter()
        freqs, h = scipy_signal.freqz(m.rlb_filter_b, m.rlb_filter_a, worN=8192, fs=SR)
        mag = 20 * np.log10(np.abs(h) + 1e-12)
        # Shelf midpoint is where gain = half_gain = ~2 dB
        half_gain = 3.999843 / 2
        idx = np.argmin(np.abs(mag - half_gain))
        shelf_mid_hz = freqs[idx]
        assert 1500.0 < shelf_mid_hz < 1900.0, (
            f"Shelf midpoint must be near 1681 Hz, got {shelf_mid_hz:.1f} Hz. "
            f"Old code would give ~1500 Hz."
        )


class TestLufsIntegration:
    def test_997hz_sine_measures_expected_lufs(self):
        """997 Hz sine at known level must measure expected LUFS within ±0.5 LU."""
        # Target: -23 LUFS. K-weighting ≈ 0 dB at 997 Hz.
        # LUFS = -0.691 + 10*log10(mean_sq) => mean_sq = 10^((-23+0.691)/10)
        target_lufs = -23.0
        mean_sq = 10 ** ((target_lufs + 0.691) / 10)
        target_rms = float(np.sqrt(mean_sq))

        m = _make_meter(sr=48000)
        audio = _sine(997.0, rms=target_rms, duration=10.0, sr=48000)
        result = _feed_and_finalize(m, audio)

        assert np.isfinite(result.integrated_lufs), "LUFS should be finite"
        assert abs(result.integrated_lufs - target_lufs) < 0.5, (
            f"Expected ~{target_lufs} LUFS, got {result.integrated_lufs:.2f}"
        )
