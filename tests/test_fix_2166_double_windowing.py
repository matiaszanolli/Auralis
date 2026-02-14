"""
Test for issue #2166: Double windowing in FFT EQ causes amplitude modulation
"""

import numpy as np
import pytest

from auralis.dsp.eq.filters import apply_eq_mono


def create_freq_to_band_map(fft_size: int, num_bands: int = 10) -> np.ndarray:
    """Create a simple frequency-to-band mapping for testing"""
    freq_bins = fft_size // 2 + 1
    return np.linspace(0, num_bands - 1, freq_bins, dtype=int)


class TestDoubleWindowingFix:
    """Test suite for verifying the double windowing fix"""

    def test_constant_amplitude_sine_wave_with_zero_db_gains(self):
        """
        Test that a constant-amplitude sine wave remains constant after EQ with 0dB gains.

        This verifies that the double windowing issue is fixed - previously the output
        would have a hanning² envelope causing ~3 dB drop and severe edge attenuation.
        """
        # Setup
        sample_rate = 44100
        duration = 1.0
        frequency = 1000  # 1 kHz sine wave
        fft_size = 2048
        num_bands = 10

        # Generate constant-amplitude sine wave
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)
        input_amplitude = np.abs(audio).max()

        # Create 0 dB gains for all bands (no EQ change expected)
        gains = np.zeros(num_bands)
        freq_to_band_map = create_freq_to_band_map(fft_size, num_bands)

        # Process through EQ
        processed = apply_eq_mono(audio, gains, freq_to_band_map, fft_size)

        # Verify output amplitude is consistent
        output_amplitude = np.abs(processed).max()

        # With 0 dB gains, output amplitude should match input (within tolerance)
        # Previously this would fail due to hanning² envelope
        amplitude_ratio_db = 20 * np.log10(output_amplitude / input_amplitude)

        # Accept within 0.1 dB as specified in test plan
        assert abs(amplitude_ratio_db) < 0.1, (
            f"Output amplitude changed by {amplitude_ratio_db:.2f} dB with 0dB gains. "
            f"Expected within ±0.1 dB. This suggests amplitude modulation from windowing."
        )

    def test_rms_consistency_with_zero_db_gains(self):
        """
        Test that RMS level is preserved through EQ with 0 dB gains.

        This is a more robust test than peak amplitude, as it measures
        the overall energy preservation across the entire signal.
        """
        # Setup
        sample_rate = 44100
        duration = 1.0
        frequency = 1000
        fft_size = 2048
        num_bands = 10

        # Generate sine wave
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)

        # Create 0 dB gains
        gains = np.zeros(num_bands)
        freq_to_band_map = create_freq_to_band_map(fft_size, num_bands)

        # Process through EQ
        processed = apply_eq_mono(audio, gains, freq_to_band_map, fft_size)

        # Calculate RMS for both signals (use same length for fair comparison)
        min_len = min(len(audio), len(processed))
        input_rms = np.sqrt(np.mean(audio[:min_len] ** 2))
        output_rms = np.sqrt(np.mean(processed[:min_len] ** 2))

        # Compare RMS levels
        rms_ratio_db = 20 * np.log10(output_rms / input_rms)

        # Accept within 0.5 dB as specified in test plan
        assert abs(rms_ratio_db) < 0.5, (
            f"Output RMS changed by {rms_ratio_db:.2f} dB with 0dB gains. "
            f"Expected within ±0.5 dB. This suggests energy loss from double windowing."
        )

    def test_no_amplitude_envelope_across_chunk(self):
        """
        Test that processed audio doesn't have a hanning² envelope.

        With the bug, the output would have maximum amplitude at the center
        and severe attenuation at edges. After the fix, amplitude should
        be relatively uniform (accounting for edge effects from windowing).
        """
        # Setup
        sample_rate = 44100
        fft_size = 2048
        num_bands = 10

        # Generate a constant amplitude signal (DC offset for simplicity)
        audio = np.ones(fft_size, dtype=np.float32) * 0.5

        # Create 0 dB gains
        gains = np.zeros(num_bands)
        freq_to_band_map = create_freq_to_band_map(fft_size, num_bands)

        # Process through EQ
        processed = apply_eq_mono(audio, gains, freq_to_band_map, fft_size)

        # Calculate amplitude at different points
        center_idx = len(processed) // 2
        quarter_idx = len(processed) // 4
        three_quarter_idx = 3 * len(processed) // 4

        center_amp = abs(processed[center_idx])
        quarter_amp = abs(processed[quarter_idx])
        three_quarter_amp = abs(processed[three_quarter_idx])

        # With the bug, center would be ~0.5 * hanning²(0.5) ≈ 0.375
        # After fix, all should be close to 0.5 (accounting for window effects)

        # The amplitudes should be reasonably close to each other
        # (not dropping to near-zero at edges as with hanning²)
        max_amp = max(center_amp, quarter_amp, three_quarter_amp)
        min_amp = min(center_amp, quarter_amp, three_quarter_amp)

        if max_amp > 0:
            amp_variation_db = 20 * np.log10(max_amp / min_amp)

            # Accept some variation due to windowing, but it shouldn't be
            # the severe ~10+ dB drop from hanning²
            assert amp_variation_db < 6.0, (
                f"Amplitude varies by {amp_variation_db:.2f} dB across chunk. "
                f"This suggests a hanning² envelope from double windowing."
            )

    def test_spectral_content_preserved_with_zero_db_gains(self):
        """
        Test that spectral content is preserved when using 0 dB gains.

        This ensures we haven't introduced new spectral leakage artifacts
        when removing the second window application.
        """
        # Setup
        sample_rate = 44100
        duration = 0.5
        frequency = 1000  # Single frequency component
        fft_size = 2048
        num_bands = 10

        # Generate pure sine wave
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)

        # Create 0 dB gains
        gains = np.zeros(num_bands)
        freq_to_band_map = create_freq_to_band_map(fft_size, num_bands)

        # Process through EQ
        processed = apply_eq_mono(audio, gains, freq_to_band_map, fft_size)

        # Compare frequency content
        # Take FFT of both signals (use same length)
        min_len = min(len(audio), len(processed))
        fft_input = np.fft.fft(audio[:min_len])
        fft_output = np.fft.fft(processed[:min_len])

        # Find dominant frequency in both
        input_peak_freq_idx = np.argmax(np.abs(fft_input[:min_len // 2]))
        output_peak_freq_idx = np.argmax(np.abs(fft_output[:min_len // 2]))

        # Peak frequency should be the same
        assert input_peak_freq_idx == output_peak_freq_idx, (
            "Peak frequency changed after EQ with 0dB gains. "
            "This suggests spectral artifacts."
        )

        # Magnitude at peak frequency should be similar
        input_peak_mag = np.abs(fft_input[input_peak_freq_idx])
        output_peak_mag = np.abs(fft_output[output_peak_freq_idx])

        if input_peak_mag > 0:
            mag_ratio_db = 20 * np.log10(output_peak_mag / input_peak_mag)

            # Accept within 1 dB (accounting for windowing differences)
            assert abs(mag_ratio_db) < 1.0, (
                f"Peak magnitude changed by {mag_ratio_db:.2f} dB. "
                f"This suggests spectral distortion."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
