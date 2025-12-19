# -*- coding: utf-8 -*-

"""
Low-Mid Transient Enhancer
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enhances transient definition in the low-mid range (150-1500 Hz) to restore
punch and clarity to instruments like bass, piano, and vocals that reach
that frequency range, especially after aggressive compression/limiting.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from scipy import signal


class LowMidTransientEnhancer:
    """
    Enhance transients in the low-mid frequency range (150-1500 Hz).

    Applies a multi-band approach:
    1. Extract low-mid band (150-1500 Hz)
    2. Detect transients via high-frequency content
    3. Apply gentle expansion around transient onsets
    4. Re-combine with full signal
    """

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize the transient enhancer.

        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate

        # Filter design for low-mid band (150-1500 Hz)
        self.low_mid_freq_low = 150
        self.low_mid_freq_high = 1500

        # Design bandpass filter for low-mid extraction
        nyquist = sample_rate / 2
        low_norm = self.low_mid_freq_low / nyquist
        high_norm = self.low_mid_freq_high / nyquist

        # Butterworth bandpass filter (4th order)
        self.b_low_mid, self.a_low_mid = signal.butter(
            4, [low_norm, high_norm], btype='band'
        )

        # High-pass filter for transient detection (>2kHz)
        hp_freq_norm = 2000 / nyquist
        self.b_hp, self.a_hp = signal.butter(2, hp_freq_norm, btype='high')

    def enhance_transients(
        self,
        audio: np.ndarray,
        intensity: float = 0.5,
        attack_samples: int = 100
    ) -> np.ndarray:
        """
        Enhance transients in low-mid frequency range.

        Args:
            audio: Input audio signal [samples] or [samples, channels]
            intensity: Enhancement strength (0.0-1.0)
                - 0.0: No enhancement
                - 0.5: Moderate enhancement
                - 1.0: Aggressive enhancement
            attack_samples: Number of samples for transient onset window

        Returns:
            Audio with enhanced low-mid transients
        """
        if intensity <= 0.0:
            return audio

        # Handle stereo vs mono
        is_stereo = audio.ndim > 1 and audio.shape[1] == 2

        if is_stereo:
            # Process each channel separately
            left = audio[:, 0].copy()
            right = audio[:, 1].copy()

            left_enhanced = self._enhance_channel(left, intensity, attack_samples)
            right_enhanced = self._enhance_channel(right, intensity, attack_samples)

            return np.column_stack([left_enhanced, right_enhanced])
        else:
            return self._enhance_channel(audio, intensity, attack_samples)

    def _enhance_channel(
        self,
        audio: np.ndarray,
        intensity: float,
        attack_samples: int
    ) -> np.ndarray:
        """Enhance transients for a single channel."""
        # Ensure audio is 1D
        if audio.ndim > 1:
            audio = audio.squeeze()

        output = audio.copy()

        # Extract low-mid band
        low_mid = signal.filtfilt(self.b_low_mid, self.a_low_mid, audio)

        # Extract high frequencies for transient detection
        high_freq = signal.filtfilt(self.b_hp, self.a_hp, audio)

        # Detect transient onsets via high-frequency energy
        # Smooth the high-frequency energy
        window_size = int(self.sample_rate * 0.01)  # 10ms window
        # Ensure odd window size for savgol_filter
        if window_size % 2 == 0:
            window_size += 1
        window_size = max(5, window_size)  # Minimum window size of 5

        high_energy = np.abs(high_freq)
        # Only use savgol_filter if we have enough samples
        if len(high_energy) >= window_size:
            energy_smoothed = signal.savgol_filter(high_energy, window_size, 3)
        else:
            energy_smoothed = high_energy

        # Find peaks in high-frequency energy (potential transients)
        threshold = np.mean(energy_smoothed) + 0.5 * np.std(energy_smoothed)
        peaks, _ = signal.find_peaks(energy_smoothed, height=threshold)

        if len(peaks) == 0:
            return output  # No transients detected

        # Apply expansion around transient onsets
        expansion_ratio = 1.0 + (2.0 * intensity)  # 1.0-3.0x expansion

        for peak_idx in peaks:
            # Window around transient
            start = max(0, peak_idx - attack_samples)
            end = min(len(audio), peak_idx + attack_samples)

            # Apply gentle expansion to low-mid in this window
            # Expansion: boost quieter parts more, preserve loud parts
            low_mid_window = low_mid[start:end]
            rms_level = np.sqrt(np.mean(low_mid_window ** 2))

            if rms_level > 1e-6:  # Avoid division by very small numbers
                # Calculate expansion envelope
                relative_level = np.abs(low_mid_window) / rms_level
                # Expand: boost ratio based on level difference from mean
                expansion_factor = np.power(relative_level, 1.0 - intensity)

                # Apply with crossfade for smoothness
                fade_in = np.linspace(0, 1, min(20, end - start))
                fade_out = np.linspace(1, 0, min(20, end - start))

                # Boost the transient window in the output
                if end - start > 0:
                    boost_amount = (expansion_ratio - 1.0) * intensity
                    output[start:end] += boost_amount * low_mid[start:end]

        # Prevent clipping
        max_val = np.max(np.abs(output))
        if max_val > 1.0:
            output = output / max_val

        return output


__all__ = ['LowMidTransientEnhancer']
