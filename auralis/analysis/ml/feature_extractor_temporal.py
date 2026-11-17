"""
Rhythm and pitch features for FeatureExtractor (split out of feature_extractor.py, #6273): tempo
stability, onset rate, harmonic ratio and fundamental frequency.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable

import numpy as np

from ...dsp.utils.spectral import (
    ANALYSIS_HOP_S,
    ANALYSIS_WINDOW_S,
    frames_for_seconds,
    tempo_estimate,
)


class TemporalFeaturesMixin:
    """The methods read the host's sample rate and averaged autocorrelation."""

    sample_rate: int
    _averaged_autocorr: Callable[[np.ndarray], np.ndarray]  # Provided by FeatureExtractor.

    def _tempo_stability(self, audio: np.ndarray) -> float:
        """Estimate tempo stability"""
        chunk_size = self.sample_rate * 2
        tempos = []

        for i in range(0, len(audio) - chunk_size, chunk_size):
            chunk = audio[i:i + chunk_size]
            tempo = tempo_estimate(chunk, self.sample_rate)
            if 60 <= tempo <= 200:
                tempos.append(tempo)

        if len(tempos) < 2:
            return 0.5

        tempo_std = float(np.std(tempos))
        tempo_mean = float(np.mean(tempos))
        return 1.0 - min(tempo_std / (tempo_mean + 1e-10), 1.0)

    def _onset_rate(self, audio: np.ndarray) -> float:
        """Estimate onset rate"""
        # Window/hop anchored in time, not bare sample counts, so onset
        # detection resolution doesn't silently drift with sample rate
        # (#4308) — 1024/512 samples at 44.1kHz.
        window_size = frames_for_seconds(self.sample_rate, ANALYSIS_WINDOW_S)
        hop_size = frames_for_seconds(self.sample_rate, ANALYSIS_HOP_S)
        onsets = 0
        prev_spectrum = None

        for i in range(0, len(audio) - window_size, hop_size):
            chunk = audio[i:i + window_size]
            spectrum = np.abs(np.fft.fft(chunk))

            if prev_spectrum is not None:
                flux = np.sum(np.maximum(spectrum - prev_spectrum, 0))
                if flux > np.mean(spectrum) * 0.1:
                    onsets += 1

            prev_spectrum = spectrum

        return onsets / (len(audio) / self.sample_rate)

    def _harmonic_ratio(self, audio: np.ndarray) -> float:
        """Estimate harmonic to non-harmonic ratio"""
        autocorr = self._averaged_autocorr(audio)

        peak_threshold = np.max(autocorr) * 0.3
        peaks = autocorr > peak_threshold

        peak_energy = np.sum(autocorr[peaks])
        total_energy = np.sum(autocorr)

        return float(peak_energy / (total_energy + 1e-10))

    def _fundamental_frequency(self, audio: np.ndarray) -> float:
        """Estimate fundamental frequency"""
        autocorr = self._averaged_autocorr(audio)

        min_lag = int(self.sample_rate / 800)
        max_lag = int(self.sample_rate / 80)

        if max_lag < len(autocorr):
            autocorr_segment = autocorr[min_lag:max_lag]
            if len(autocorr_segment) > 0:
                peak_lag = np.argmax(autocorr_segment) + min_lag
                return self.sample_rate / peak_lag

        return 0.0
