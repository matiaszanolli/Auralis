"""
Spectrum analysis and adaptive gain calculation for PsychoacousticEQ (split
from psychoacoustic_eq.py, #5838): FFT magnitude and band energies, masking-
aware target gains, and the smoothing that carries gains across chunks.
"""

import threading
from typing import Any

import numpy as np

from ..utils.adaptive import smooth_parameter_transition
from ..utils.audio_info import to_mono
from .curves import apply_content_adaptation


class SpectrumGainsMixin:
    """State is created by PsychoacousticEQ.__init__."""

    sample_rate: int
    fft_size: int
    settings: Any
    critical_bands: Any
    freq_to_band_map: Any
    masking_calculator: Any
    current_gains: np.ndarray
    _analysis_window: np.ndarray
    _analysis_window_gain: float
    _state_lock: "threading.Lock"

    def analyze_spectrum(self, audio_chunk: np.ndarray) -> dict[str, np.ndarray]:
        """
        Analyze audio spectrum for adaptive EQ

        Args:
            audio_chunk: Audio data for analysis

        Returns:
            Dictionary with spectrum analysis results containing:
                - magnitude_db: Magnitude spectrum in dB
                - band_energies: Energy per critical band
                - masking_thresholds: Masking thresholds per band
                - spectrum: Complex spectrum
        """
        audio_mono = to_mono(audio_chunk)

        # Ensure we have enough samples
        if len(audio_mono) < self.fft_size:
            # Pad with zeros — dtype-preserving to avoid float64 promotion.
            padded = np.zeros(self.fft_size, dtype=audio_mono.dtype)
            padded[:len(audio_mono)] = audio_mono
            audio_mono = padded

        # #4101: window the ANALYSIS FFT (only) with a Hann window plus
        # coherent-gain compensation. #3663 dropped the window so the analysis
        # spectrum matched the un-windowed apply_eq_gains frame, but the analysis
        # band energies feed the masking calculator, where the rectangular
        # window's -13 dB first sidelobe leaks bass energy into adjacent critical
        # bands and biases the masking decision (over-cutting bass-adjacent
        # bands). The window suppresses that leakage. Dividing by the coherent
        # gain (mean of the window) keeps the absolute magnitude scale equal to
        # the un-windowed path, so band *ratios* are corrected for masking
        # WITHOUT re-introducing the global +6.02 dB magnitude offset that #3428
        # reverted (which skewed adaptive gains and fingerprint LUFS/crest).
        # apply_eq_gains stays un-windowed (filters.py) — it must match the
        # signal frame it processes.
        from scipy.fft import fft
        frame = audio_mono[:self.fft_size]
        window = self._analysis_window.astype(frame.dtype, copy=False)
        windowed = (frame * window) / self._analysis_window_gain
        spectrum = fft(windowed)
        magnitude = np.abs(spectrum[:self.fft_size // 2 + 1])

        magnitude_db = 20 * np.log10(magnitude + 1e-10)

        # Calculate energy in each critical band
        band_energies = self._calculate_band_energies(magnitude_db)

        # Calculate masking thresholds
        masking_thresholds = self.masking_calculator.calculate_masking(
            magnitude, self.critical_bands, self.sample_rate
        )

        return {
            'magnitude_db': magnitude_db,
            'band_energies': band_energies,
            'masking_thresholds': masking_thresholds,
            'spectrum': spectrum
        }

    def _calculate_band_energies(self, magnitude_db: np.ndarray) -> np.ndarray:
        """Calculate energy in each critical band"""
        band_energies = np.zeros(len(self.critical_bands))
        for i, band in enumerate(self.critical_bands):
            band_mask = self.freq_to_band_map == i
            if np.any(band_mask):
                band_energies[i] = np.mean(magnitude_db[band_mask])
        return band_energies

    def calculate_adaptive_gains(self,
                                spectrum_analysis: dict[str, Any],
                                target_curve: np.ndarray,
                                content_profile: dict[str, Any] | None = None) -> np.ndarray:
        """
        Calculate adaptive EQ gains based on spectrum analysis

        Args:
            spectrum_analysis: Results from analyze_spectrum
            target_curve: Target frequency response curve
            content_profile: Optional content analysis for adaptation

        Returns:
            Array of gain values in dB for each critical band
        """
        band_energies = spectrum_analysis['band_energies']
        masking_thresholds = spectrum_analysis['masking_thresholds']

        # Calculate initial gains based on target curve
        target_gains = self._calculate_target_gains(
            band_energies,
            masking_thresholds,
            target_curve
        )

        # Content-aware adaptation
        if content_profile:
            target_gains = apply_content_adaptation(
                target_gains,
                content_profile,
                self.critical_bands
            )

        # Smooth transitions to avoid artifacts
        adaptive_gains = self._smooth_gains(target_gains)

        return adaptive_gains

    def _calculate_target_gains(self,
                               band_energies: np.ndarray,
                               masking_thresholds: np.ndarray,
                               target_curve: np.ndarray) -> np.ndarray:
        """Calculate target gains for each band.

        ``target_curve`` contains *relative* dB gains (boost/cut) per band,
        NOT absolute magnitude levels.  The previous formula
        ``target_level - current_level`` treated them as absolute targets,
        producing nonsensical gains (e.g. 3 - 40 = -37) that were silently
        clipped to -12 dB, causing a systematic ~3 dB excess cut (#3428).

        Now: ``required_gain = target_level`` directly, with masking-aware
        attenuation applied only when the band energy is below the masking
        threshold (i.e. boosting a masked band is wasteful).
        """
        target_gains = np.zeros(len(self.critical_bands))

        # Guard against NaN/Inf from silent audio or log10(0) (fixes #2513)
        band_energies = np.where(np.isfinite(band_energies), band_energies, 0.0)
        masking_thresholds = np.where(np.isfinite(masking_thresholds), masking_thresholds, 0.0)

        for i, band in enumerate(self.critical_bands):
            # target_curve values are relative dB gains (boost/cut)
            required_gain = target_curve[i] if i < len(target_curve) else 0.0

            # Apply masking-aware adjustment: reduce boost for masked bands
            current_level = band_energies[i]
            masking_threshold = masking_thresholds[i]
            if current_level < masking_threshold:
                required_gain *= 0.5

            # Apply perceptual weighting
            weighted_gain = required_gain * band.weight

            target_gains[i] = np.clip(weighted_gain, -12.0, 12.0)  # Limit gain range

        return target_gains

    def _smooth_gains(self, target_gains: np.ndarray) -> np.ndarray:
        """Smooth gain transitions to avoid artifacts (#3747: locked).

        Reads and writes `self.current_gains` — atomic under the
        state lock so concurrent callers see consistent inter-chunk
        smoothing (the prior unprotected read-modify-write would
        produce jittery band-EQ wobble under shared-instance use)."""
        with self._state_lock:
            adaptive_gains = np.zeros_like(target_gains)
            for i in range(len(target_gains)):
                adaptive_gains[i] = smooth_parameter_transition(
                    self.current_gains[i],
                    target_gains[i],
                    self.settings.adaptation_speed
                )

            # Update current gains
            self.current_gains = adaptive_gains.copy()

            return adaptive_gains
