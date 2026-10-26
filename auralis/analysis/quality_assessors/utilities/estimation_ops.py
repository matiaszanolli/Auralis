"""
Estimation Operations
~~~~~~~~~~~~~~~~~~~~~

Common signal estimation patterns for quality assessments.

Provides shared estimation functions used across all quality assessors
to ensure consistency and reduce code duplication.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


import numpy as np

from ....dsp.utils.audio_info import to_mono


class EstimationOperations:
    """Common signal estimation patterns"""

    # estimate_thd: what counts as a dominant fundamental (#5714)
    _THD_PEAK_HALF_WIDTH = 2          # Hann main lobe is +/-2 bins
    _THD_MIN_FUNDAMENTAL_SHARE = 0.10  # of total spectral power
    _THD_MIN_PEAK_TO_MEDIAN_DB = 30.0  # white noise peaks only ~12 dB up

    # estimate_noise_floor / estimate_snr_db
    _NOISE_FFT = 4096
    _SILENT_SNR_DB = 120.0

    @staticmethod
    def estimate_thd(audio: np.ndarray,
                     fundamental_idx: int | None = None) -> float | None:
        """
        Estimate Total Harmonic Distortion of a tonal signal

        THD is only defined when the signal has a dominant fundamental whose
        harmonics can be told apart from the rest of the spectrum. Programme
        material has no such fundamental: the largest FFT bin of a mix is an
        arbitrary partial, and the power at 2f..5f is other instruments, so
        the ratio measures nothing (white Gaussian noise "scored" 0.36, #5714).
        The ratio is therefore reported only when the strongest spectral peak
        holds at least ``_THD_MIN_FUNDAMENTAL_SHARE`` of the spectral power
        and stands ``_THD_MIN_PEAK_TO_MEDIAN_DB`` above the median bin;
        otherwise the result is ``None`` ("not applicable") and callers leave
        the term out of their score instead of rating it 0.

        Peak power is integrated over +/- ``_THD_PEAK_HALF_WIDTH`` bins of a
        Hann-windowed spectrum so a tone that falls between bins is not
        under-counted.

        Args:
            audio: Audio data (mono or stereo)
            fundamental_idx: Optional pre-computed fundamental frequency index

        Returns:
            THD as ratio (0-1+), or ``None`` when not applicable (degenerate
            length, no dominant tone, or no harmonic inside the spectrum)
        """
        audio_mono = to_mono(audio)

        # Use middle section for analysis (avoid silence at start/end)
        mid_start = len(audio_mono) // 4
        mid_end = 3 * len(audio_mono) // 4
        audio_segment = audio_mono[mid_start:mid_end]

        # #4996: len(audio_mono) in {0, 1} yields an empty middle section,
        # and np.fft.rfft raises ValueError on a 0-length array. THD is
        # undefined for degenerate input.
        if len(audio_segment) < 2:
            return None

        magnitude = np.abs(np.fft.rfft(audio_segment * np.hanning(len(audio_segment))))
        n_bins = len(magnitude)
        search_lo, search_hi = 10, n_bins // 2
        if search_hi <= search_lo:
            return None

        # Estimate fundamental frequency if not provided
        if fundamental_idx is None:
            fundamental_idx = int(np.argmax(magnitude[search_lo:search_hi]) + search_lo)

        power = magnitude ** 2
        total_power = float(np.sum(power[1:]))
        median_power = float(np.median(power[1:]))
        half = EstimationOperations._THD_PEAK_HALF_WIDTH

        def peak_power(idx: int) -> float:
            return float(np.sum(power[max(idx - half, 0):idx + half + 1]))

        fundamental_power = peak_power(fundamental_idx)
        if total_power <= 0 or fundamental_power <= 0:
            return None
        if fundamental_power / total_power < EstimationOperations._THD_MIN_FUNDAMENTAL_SHARE:
            return None
        peak_db = 10 * np.log10(power[fundamental_idx] / max(median_power, 1e-30))
        if peak_db < EstimationOperations._THD_MIN_PEAK_TO_MEDIAN_DB:
            return None

        # Estimate harmonic power (2nd to 5th harmonics).
        # #3678: only include harmonics whose theoretical index falls within
        # the valid spectrum — clamping to the Nyquist bin made harmonic
        # power meaningless for bright content.
        max_bin = n_bins - 1
        harmonic_power = 0.0
        n_harmonics_used = 0
        for i in range(2, 6):  # 2nd to 5th harmonics
            harmonic_idx = fundamental_idx * i
            if harmonic_idx <= max_bin:
                harmonic_power += peak_power(harmonic_idx)
                n_harmonics_used += 1

        # No harmonic fits below Nyquist: THD is undefined.
        if n_harmonics_used == 0:
            return None

        return float(np.sqrt(harmonic_power / fundamental_power))

    @staticmethod
    def detect_clipping(audio: np.ndarray,
                       threshold: float = 0.99) -> float:
        """
        Detect audio clipping

        Counts samples at or near digital maximum (0 dBFS).

        Args:
            audio: Audio data
            threshold: Clipping threshold (default 0.99, normalized amplitude)

        Returns:
            Clipping factor (0-1, higher means more clipping)
        """
        clipped_samples = np.sum(np.abs(audio) >= threshold)
        total_samples = audio.size

        clipping_factor = clipped_samples / total_samples if total_samples > 0 else 0.0

        return float(clipping_factor)

    @staticmethod
    def estimate_noise_floor(audio: np.ndarray,
                            silence_threshold: float = 1e-6,
                            percentile: int = 10) -> float:
        """
        Estimate the spectral noise floor

        Returns the level (dBFS) of the white noise whose power spectral
        density equals the ``percentile``-th lowest bin of the long-term
        spectrum. Tonal and band-limited programme occupies only part of the
        spectrum, so the quiet bins expose the background underneath it; the
        previous estimate (mean of the lowest 10 % of ``|x|``) was just the
        near-zero-crossing part of the programme's own amplitude distribution
        and tracked its level 1:1 (#5714).

        The result is an absolute level, so it moves with gain like the signal
        does. Use :meth:`estimate_snr_db` for a level-independent figure.

        Args:
            audio: Audio data (mono or stereo)
            silence_threshold: Minimum amplitude considered (default 1e-6)
            percentile: Percentile of the long-term spectrum (default 10)

        Returns:
            Noise floor in dBFS
        """
        audio_mono = to_mono(audio)
        if len(audio_mono) == 0:
            return -90.0

        n_fft = EstimationOperations._NOISE_FFT
        window = np.hanning(n_fft)
        hop = n_fft // 2
        padded = audio_mono
        if len(padded) < n_fft:
            padded = np.pad(padded, (0, n_fft - len(padded)))
        n_frames = 1 + (len(padded) - n_fft) // hop

        # Accumulate the Welch PSD in batches so a full-length track never
        # materialises every frame at once.
        psd_sum = np.zeros(n_fft // 2 + 1)
        batch = 256
        for first in range(0, n_frames, batch):
            idx = np.arange(first, min(first + batch, n_frames))
            frames = padded[idx[:, None] * hop + np.arange(n_fft)] * window
            psd_sum += np.sum(np.abs(np.fft.rfft(frames, axis=1)) ** 2, axis=0)

        # Normalised so a white signal of variance s^2 reads s^2 in every bin.
        psd = psd_sum / (n_frames * float(np.sum(window ** 2)))
        floor_power = float(np.percentile(psd[1:], percentile))
        noise_level = max(float(np.sqrt(floor_power)), silence_threshold)
        return float(20 * np.log10(noise_level))

    @staticmethod
    def estimate_snr_db(audio: np.ndarray,
                        silence_threshold: float = 1e-6) -> float:
        """
        Programme level over the spectral noise floor, in dB

        Both terms scale with gain, so the difference does not: the same
        recording at -20 dBFS and -6 dBFS reports the same SNR. Digital
        silence has nothing to measure noise against and reports
        ``_SILENT_SNR_DB``.
        """
        audio_mono = to_mono(audio)
        rms = float(np.sqrt(np.mean(audio_mono ** 2))) if len(audio_mono) else 0.0
        if rms <= silence_threshold:
            return EstimationOperations._SILENT_SNR_DB
        noise_floor_db = EstimationOperations.estimate_noise_floor(
            audio_mono, silence_threshold
        )
        return float(max(20 * np.log10(rms) - noise_floor_db, 0.0))

    @staticmethod
    def compute_stereo_correlation(left: np.ndarray,
                                  right: np.ndarray) -> float:
        """
        Compute stereo correlation coefficient

        Measures how similar left and right channels are.
        1.0 = identical, 0.0 = uncorrelated, -1.0 = inverse

        Args:
            left: Left channel audio
            right: Right channel audio

        Returns:
            Correlation coefficient (-1 to 1)
        """
        # Ensure same length
        min_len = min(len(left), len(right))
        left = left[:min_len]
        right = right[:min_len]

        # Normalize
        left_norm = left - np.mean(left)
        right_norm = right - np.mean(right)

        # Compute correlation
        numerator = np.sum(left_norm * right_norm)
        denominator = np.sqrt(np.sum(left_norm ** 2) * np.sum(right_norm ** 2))

        if denominator == 0:
            return 0.0

        correlation = numerator / denominator

        return float(np.clip(correlation, -1.0, 1.0))
