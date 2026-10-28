"""BS.1770-4 K-weighting coefficient regression tests (#4213).

Verifies that LoudnessMeter uses the correct ITU-R BS.1770-4 parameters:
  - High-shelf at 1681.974 Hz +3.999843 dB  (was 1500 Hz +4 dB)
  - 2nd-order RLB HP at 38.135 Hz, Q ~ 0.5003 (was 1st-order 40 Hz, then a Butterworth, #5593)
"""
import numpy as np
import pytest
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

    def test_hp_is_the_rlb_filter_not_a_butterworth(self):
        """The RLB high-pass is critically damped (Q ~ 0.5003): -6 dB at 38 Hz, not the
        Butterworth's -3 dB (#5593). Its poles must sit where the standard puts them."""
        m = _make_meter()
        _, h = scipy_signal.freqz(m.pre_filter_b, m.pre_filter_a, worN=[38.135], fs=SR)
        assert 20 * np.log10(abs(h[0])) == pytest.approx(-6.02, abs=0.15)
        poles = np.roots(m.pre_filter_a)
        assert poles[0].imag == pytest.approx(0.0, abs=1e-3)  # a double real pole, not a conjugate pair

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

    def test_coefficients_match_the_standard_at_48khz(self):
        """BS.1770-4 Annex 1 tabulates the 48 kHz coefficients (#5593)."""
        m = _make_meter(sr=48000)
        np.testing.assert_allclose(
            m.rlb_filter_b, [1.53512485958697, -2.69169618940638, 1.19839281085285], atol=1e-9
        )
        np.testing.assert_allclose(m.rlb_filter_a, [1.0, -1.69065929318241, 0.73248077421585], atol=1e-9)
        np.testing.assert_allclose(m.pre_filter_b, [1.0, -2.0, 1.0], atol=1e-12)
        np.testing.assert_allclose(m.pre_filter_a, [1.0, -1.99004745483398, 0.99007225036621], atol=1e-9)

    def test_chain_gain_at_1khz_is_the_standards_0_691_db(self):
        """The -0.691 LUFS offset exists to cancel the chain's +0.691 dB at ~1 kHz.
        Other rates are the bilinear transform of the same prototype, so they agree to a few
        hundredths of a dB."""
        for sr in (44100, 48000, 96000):
            m = _make_meter(sr=sr)
            _, h_hp = scipy_signal.freqz(m.pre_filter_b, m.pre_filter_a, worN=[997.0], fs=sr)
            _, h_sh = scipy_signal.freqz(m.rlb_filter_b, m.rlb_filter_a, worN=[997.0], fs=sr)
            assert 20 * np.log10(abs(h_hp[0] * h_sh[0])) == pytest.approx(0.691, abs=0.03)


class TestLufsIntegration:
    def test_997hz_sine_measures_expected_lufs(self):
        """997 Hz sine at known level must measure expected LUFS within ±0.5 LU."""
        # BS.1770 calibration: the K-weighting chain gains +0.691 dB at 997 Hz and the
        # -0.691 offset cancels it, so a 997 Hz sine reads its own RMS level in LUFS.
        target_lufs = -23.0
        target_rms = 10 ** (target_lufs / 20)

        m = _make_meter(sr=48000)
        audio = _sine(997.0, rms=target_rms, duration=10.0, sr=48000)
        result = _feed_and_finalize(m, audio)

        assert np.isfinite(result.integrated_lufs), "LUFS should be finite"
        assert abs(result.integrated_lufs - target_lufs) < 0.05, (
            f"Expected ~{target_lufs} LUFS, got {result.integrated_lufs:.2f}"
        )
