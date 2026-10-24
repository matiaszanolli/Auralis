"""
Low-Mid Transient Enhancer
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enhances transient definition in the low-mid range (150-1500 Hz) to restore
punch and clarity to instruments like bass, piano, and vocals that reach
that frequency range, especially after aggressive compression/limiting.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
from scipy import signal

from .soft_clipper import soft_clip


class LowMidTransientEnhancer:
    """
    Enhance transients in the low-mid frequency range (150-1500 Hz).

    Applies a multi-band approach:
    1. Extract low-mid band (150-1500 Hz)
    2. Detect transients via high-frequency content
    3. Apply gentle expansion around transient onsets
    4. Re-combine with full signal
    """

    def __init__(self, sample_rate: int):
        """
        Initialize the transient enhancer.

        Args:
            sample_rate: Audio sample rate in Hz. Required (#4622) — the
                bandpass filter design below derives its edges from it, so a
                missing/wrong value silently mis-places the low-mid band.
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
            return audio.copy()

        # 1-D mono and 2-D [samples, channels] are both processed per
        # channel; the input shape (including (n, 1)) is returned unchanged
        # (#6104) — the old stereo-only branch squeezed (n, 1) down to (n,).
        if audio.ndim == 1:
            return self._enhance_channel(audio, intensity, attack_samples)
        if audio.ndim != 2:
            raise ValueError(f"Expected 1-D or 2-D audio, got shape {audio.shape}")
        return np.column_stack([
            self._enhance_channel(audio[:, ch], intensity, attack_samples)
            for ch in range(audio.shape[1])
        ])

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

        # A window wider than the buffer spans the whole buffer for every
        # peak. The realtime call site passes 50 ms at 44.1 kHz (2205
        # samples) against 1024-sample buffers (#6104), so clamp to the
        # buffer length to keep the window meaningful at any chunk size.
        attack = min(attack_samples, len(audio))

        # Per-peak windows overlapping on the same sample used to be summed,
        # so a buffer with K detected peaks got K stacked boosts — ~+20 dB
        # of low-mid and hard clipping per realtime buffer (#6104). Each
        # sample now receives at most one window's worth of expansion: the
        # strongest window wins. Uncovered samples stay at 0 (untouched),
        # which also preserves the single-window behaviour exactly.
        contribution = np.full(len(audio), -np.inf, dtype=low_mid.dtype)

        for peak_idx in peaks:
            # Window around transient
            start = max(0, peak_idx - attack)
            end = min(len(audio), peak_idx + attack)

            # Apply gentle expansion to low-mid in this window
            # Expansion: boost quieter parts more, preserve loud parts
            low_mid_window = low_mid[start:end]
            rms_level = np.sqrt(np.mean(low_mid_window ** 2))

            if rms_level <= 1e-6:  # Avoid division by very small numbers
                continue

            # Calculate expansion envelope (level-dependent gain)
            relative_level = np.abs(low_mid_window) / rms_level
            expansion_env = np.power(relative_level, 1.0 - intensity)

            window_len = end - start
            if window_len <= 0:
                continue

            # Crossfade ramps for smooth attack/release at window edges
            ramp_len = min(20, window_len)
            fade_in = np.linspace(0, 1, ramp_len)
            fade_out = np.linspace(1, 0, ramp_len)

            # Build blend envelope: ramp up at start, ramp down at end
            blend = np.ones(window_len)
            blend[:ramp_len] = np.minimum(blend[:ramp_len], fade_in)
            blend[window_len - ramp_len:] = np.minimum(
                blend[window_len - ramp_len:], fade_out
            )

            np.maximum(
                contribution[start:end],
                (expansion_env * expansion_ratio - 1.0) * blend,
                out=contribution[start:end],
            )

        contribution[~np.isfinite(contribution)] = 0.0

        # One bounded expansion per sample, never K stacked ones
        output += low_mid * contribution

        # Soft saturation as the safety net instead of a hard clip (#6104):
        # tanh above the threshold leaves sub-threshold samples bit-exact
        # and bounds the peak below the ceiling without the discontinuity
        # of np.clip. The old hard clip was the only thing capping the
        # stacked windows (fixes #2682's clip; see also #2202).
        return soft_clip(output)


__all__ = ['LowMidTransientEnhancer']
