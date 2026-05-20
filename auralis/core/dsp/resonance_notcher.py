"""
Resonance Notcher
~~~~~~~~~~~~~~~~~

Detect narrow spectral peaks in a recording and apply surgical notches to tame
them. Designed for live recordings where room modes (typically in 150-1000 Hz)
hog 10-15 dB above the surrounding spectrum, masking midrange detail.

Two-step usage:
    notches = ResonanceNotcher.detect(sample_segment, sample_rate)
    cleaned = ResonanceNotcher.apply(audio, sample_rate, notches)

Detection is expensive (FFT + peak-finding), so it's run *once* per file on a
representative segment. Application is cheap (cascaded biquads) and runs per
chunk.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks, sosfiltfilt, tf2sos


@dataclass(frozen=True)
class Notch:
    """A single notch to apply: a narrow cut at `freq_hz` of `depth_db` (negative)."""
    freq_hz: float
    depth_db: float  # negative — e.g. -4.0 for a 4 dB cut
    q: float = 6.0   # Q ~ 6 = roughly 1/6 octave wide

    @property
    def gain_linear(self) -> float:
        """Linear gain to apply at the notch frequency (< 1.0)."""
        return 10.0 ** (self.depth_db / 20.0)


class ResonanceNotcher:
    """Detect and apply narrow-band cuts to tame spectral resonances."""

    @staticmethod
    def detect(
        audio: np.ndarray,
        sample_rate: int,
        min_freq: float = 150.0,
        max_freq: float = 1200.0,
        min_prominence_db: float = 8.0,
        max_notches: int = 5,
        max_depth_db: float = -5.0,
    ) -> list[Notch]:
        """
        Find narrow spectral peaks that stand out from the local spectral floor.

        Args:
            audio: Mono or stereo audio. Stereo is summed to mono internally.
            sample_rate: Sample rate in Hz.
            min_freq, max_freq: Search range. Default 150-1200 Hz covers the
                "mud/honk" region where room modes cause masking. Above 1.2 kHz
                resonances are usually instrument timbre, not problems.
            min_prominence_db: Minimum peak prominence vs local spectral floor
                to count as a resonance. 8 dB is conservative — won't notch
                ordinary musical content.
            max_notches: Cap the number of notches returned. Stacking too many
                narrow cuts thins the sound.
            max_depth_db: Strongest cut allowed. -5 dB is enough to relieve
                masking without making the mix sound notched-out.

        Returns:
            List of Notch objects, sorted by descending prominence.
        """
        # Reduce to mono (analysis only — we don't return modified audio here)
        if audio.ndim == 2:
            # Could be (channels, samples) or (samples, channels). Take whichever
            # axis has 2 and average across it.
            if audio.shape[0] == 2:
                mono = audio.mean(axis=0)
            else:
                mono = audio.mean(axis=1)
        else:
            mono = audio

        # Welch-style averaged PSD
        N = 16384
        if len(mono) < N:
            return []
        hop = N // 2
        hann = np.hanning(N)
        psd = np.zeros(N // 2 + 1)
        count = 0
        for i in range(0, len(mono) - N, hop):
            spec = np.fft.rfft(mono[i:i + N] * hann)
            psd += spec.real ** 2 + spec.imag ** 2
            count += 1
        if count == 0:
            return []
        psd /= count
        freqs = np.fft.rfftfreq(N, 1.0 / sample_rate)

        # Convert to dB, smooth 3-bin for stable peaks
        log_psd = 10.0 * np.log10(psd + 1e-12)
        smooth = np.convolve(log_psd, np.ones(3) / 3.0, mode='same')

        # Restrict to the search range
        mask = (freqs >= min_freq) & (freqs <= max_freq)
        if not mask.any():
            return []
        sub = smooth[mask]
        sub_f = freqs[mask]

        # find_peaks with prominence gives us "how much does this peak stick out
        # of its local neighbourhood" — exactly the masking metric we want.
        # distance=10 bins ≈ 27 Hz at sr=44100 — keeps clusters of bins from
        # being reported as separate peaks.
        peaks, props = find_peaks(sub, prominence=min_prominence_db, distance=10)
        if len(peaks) == 0:
            return []

        # Sort by prominence, descending, take the top N
        order = np.argsort(props['prominences'])[::-1][:max_notches]

        # Map prominence (dB above floor) → notch depth (negative dB).
        # 8 dB prominence → -3 dB cut; 20 dB prominence → -5 dB cut. Smooth.
        notches: list[Notch] = []
        for i in order:
            f = float(sub_f[peaks[i]])
            prom = float(props['prominences'][i])
            # Smooth ramp from min_prominence_db (-> -3 dB) to 20 dB (-> max cut)
            depth_factor = min(1.0, (prom - min_prominence_db) / max(20.0 - min_prominence_db, 1e-6))
            depth_db = -3.0 + (max_depth_db - (-3.0)) * depth_factor
            notches.append(Notch(freq_hz=f, depth_db=depth_db))

        return notches

    @staticmethod
    def apply(
        audio: np.ndarray,
        sample_rate: int,
        notches: list[Notch],
    ) -> np.ndarray:
        """
        Apply a list of notches to the audio.

        Implemented as cascaded biquad peaking-EQ cuts. Uses zero-phase
        filtering (sosfiltfilt) so notches don't introduce phase distortion
        that smears transients — these are surgical fixes, not creative tone-shaping.

        Args:
            audio: (channels, samples) or (samples,)
            sample_rate: Sample rate in Hz
            notches: List of Notch objects from detect()

        Returns:
            Audio with notches applied. Same shape and dtype as input.
        """
        if not notches:
            return audio

        out = audio.astype(audio.dtype, copy=True)
        nyq = sample_rate / 2.0
        axis = -1 if out.ndim > 1 else 0

        for n in notches:
            if n.freq_hz <= 20.0 or n.freq_hz >= nyq * 0.95:
                continue
            # Build a peaking-EQ biquad cut using the standard RBJ formula.
            # We use sosfiltfilt below for zero phase, which applies the
            # filter forward and backward → effective cut is 2× the per-pass
            # depth. Halve the depth here so the user-visible Notch.depth_db
            # matches the actual attenuation at the center frequency.
            per_pass_db = n.depth_db / 2.0
            w0 = 2.0 * np.pi * n.freq_hz / sample_rate
            cos_w0 = np.cos(w0)
            sin_w0 = np.sin(w0)
            A = 10.0 ** (per_pass_db / 40.0)
            alpha = sin_w0 / (2.0 * n.q)

            b0 = 1 + alpha * A
            b1 = -2 * cos_w0
            b2 = 1 - alpha * A
            a0 = 1 + alpha / A
            a1 = -2 * cos_w0
            a2 = 1 - alpha / A

            b = np.array([b0, b1, b2]) / a0
            a = np.array([1.0, a1 / a0, a2 / a0])
            sos = tf2sos(b, a)

            # sosfiltfilt for zero phase. Cast back to preserve dtype (NumPy
            # would otherwise promote to float64 — same issue as parallel_eq.py).
            out = np.asarray(sosfiltfilt(sos, out, axis=axis), dtype=out.dtype)

        return out
