"""
Audio Fingerprint Analyzer

Unified analyzer that extracts a complete 25D fingerprint from audio.

Combines:
  - Frequency analysis (7D): sub-bass, bass, low-mid, mid, upper-mid, presence, air
  - Dynamics analysis (3D): LUFS, crest factor, bass/mid ratio
  - Temporal analysis (4D): tempo, rhythm stability, transient density, silence ratio
  - Spectral analysis (3D): spectral centroid, rolloff, flatness
  - Harmonic analysis (3D): harmonic ratio, pitch stability, chroma energy
  - Variation analysis (3D): dynamic range variation, loudness variation, peak consistency
  - Stereo analysis (2D): stereo width, phase correlation

Total: 25 dimensions capturing frequency, dynamics, temporal, spectral, harmonic, variation, and stereo characteristics.

Dependencies:
  - numpy for numerical operations
  - librosa for advanced audio analysis
  - All individual analyzer modules
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal

import numpy as np

from auralis.analysis.fingerprint.analyzers.batch.harmonic import HarmonicAnalyzer
from auralis.analysis.fingerprint.analyzers.batch.harmonic_sampled import (
    SampledHarmonicAnalyzer,
)
from auralis.analysis.fingerprint.analyzers.batch.spectral import SpectralAnalyzer
from auralis.analysis.fingerprint.analyzers.batch.stereo import StereoAnalyzer
from auralis.analysis.fingerprint.analyzers.batch.temporal import TemporalAnalyzer
from auralis.analysis.fingerprint.analyzers.batch.variation import VariationAnalyzer

logger = logging.getLogger(__name__)


class AudioFingerprintAnalyzer:
    """Extract complete 25D audio fingerprint."""

    def __init__(self,
                 fingerprint_strategy: Literal["full-track", "sampling"] = "sampling",
                 sampling_interval: float = 20.0):
        """
        Initialize all sub-analyzers.

        Args:
            fingerprint_strategy: "full-track" or "sampling" (Phase 7)
            sampling_interval: Interval between chunk starts in seconds (for sampling)
        """
        self.temporal_analyzer = TemporalAnalyzer()
        self.spectral_analyzer = SpectralAnalyzer()
        self.harmonic_analyzer = HarmonicAnalyzer()
        self.sampled_harmonic_analyzer = SampledHarmonicAnalyzer(
            chunk_duration=5.0,
            interval_duration=sampling_interval
        )
        self.variation_analyzer = VariationAnalyzer()
        self.stereo_analyzer = StereoAnalyzer()

        self.fingerprint_strategy = fingerprint_strategy
        self.sampling_interval = sampling_interval

        logger.debug(f"AudioFingerprintAnalyzer initialized with strategy={fingerprint_strategy}")

    def analyze(self, audio: np.ndarray, sr: int) -> dict[str, float]:
        """
        Extract complete 25D audio fingerprint.

        Args:
            audio: Audio signal (stereo or mono)
            sr: Sample rate

        Returns:
            Dict with 25 fingerprint features:

            Frequency (7D):
              - sub_bass_pct: 20-60 Hz energy percentage
              - bass_pct: 60-250 Hz energy percentage
              - low_mid_pct: 250-500 Hz energy percentage
              - mid_pct: 500-2000 Hz energy percentage
              - upper_mid_pct: 2000-4000 Hz energy percentage
              - presence_pct: 4000-6000 Hz energy percentage
              - air_pct: 6000-20000 Hz energy percentage

            Dynamics (3D):
              - lufs: Integrated loudness (ITU-R BS.1770-4)
              - crest_db: Peak-to-RMS ratio in dB
              - bass_mid_ratio: Bass/Mid energy ratio in dB

            Temporal (4D):
              - tempo_bpm: Detected tempo
              - rhythm_stability: Beat consistency (0-1)
              - transient_density: Drum/percussion prominence (0-1)
              - silence_ratio: Silence/space proportion (0-1)

            Spectral (3D):
              - spectral_centroid: Brightness (0-1)
              - spectral_rolloff: High-frequency content (0-1)
              - spectral_flatness: Noise-like vs tonal (0-1)

            Harmonic (3D):
              - harmonic_ratio: Harmonic vs percussive (0-1)
              - pitch_stability: Pitch consistency (0-1)
              - chroma_energy: Tonal complexity (0-1)

            Variation (3D):
              - dynamic_range_variation: Crest factor std dev over time (0-1)
              - loudness_variation_std: Loudness consistency (0-1)
              - peak_consistency: Peak level consistency (0-1)

            Stereo (2D):
              - stereo_width: Mono (0) to wide stereo (1)
              - phase_correlation: -1 (out of phase) to +1 (in phase)
        """
        try:
            # Convert to mono for most analysis (except stereo analyzer)
            if len(audio.shape) > 1:
                audio_mono = np.mean(audio, axis=0) if audio.shape[0] == 2 else np.mean(audio, axis=1)
            else:
                audio_mono = audio

            # Initialize fingerprint dict
            fingerprint: dict[str, Any] = {}

            # OPTIMIZATION: Pre-compute FFT and RMS once, reuse for frequency/dynamics/variation
            fft = np.fft.rfft(audio_mono)
            magnitude = np.abs(fft)
            freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)
            rms = np.sqrt(np.mean(audio_mono ** 2))

            # 1. Frequency analysis (7D)
            frequency_features = self._analyze_frequency_cached(audio_mono, sr, fft, magnitude, freqs)
            fingerprint.update(frequency_features)

            # 2. Dynamics analysis (3D)
            dynamics_features = self._analyze_dynamics_cached(audio_mono, sr, fft, magnitude, freqs, rms)
            fingerprint.update(dynamics_features)

            # OPTIMIZATION: Parallelize remaining analyzers (3-7) with ThreadPoolExecutor
            # Analyzers 1-2 (frequency/dynamics) depend on pre-computed FFT, run sequentially first
            # Analyzers 3-7 are independent and can run concurrently

            # Harmonic analyzer selection
            harmonic_analyzer = (self.sampled_harmonic_analyzer
                                if self.fingerprint_strategy == "sampling"
                                else self.harmonic_analyzer)

            # Run independent analyzers in parallel.
            # Avoid the `with` context manager: its __exit__ calls shutdown(wait=True),
            # which blocks indefinitely on KeyboardInterrupt while threads are running.
            executor = ThreadPoolExecutor(max_workers=5)
            try:
                futures = {
                    # 3. Temporal analysis (4D)
                    executor.submit(self.temporal_analyzer.analyze, audio_mono, sr): 'temporal',

                    # 4. Spectral analysis (3D)
                    executor.submit(self.spectral_analyzer.analyze, audio_mono, sr): 'spectral',

                    # 5. Harmonic analysis (3D)
                    executor.submit(harmonic_analyzer.analyze, audio_mono, sr): 'harmonic',

                    # 6. Variation analysis (3D)
                    executor.submit(self.variation_analyzer.analyze, audio_mono, sr): 'variation',

                    # 7. Stereo analysis (2D) - uses original stereo audio
                    executor.submit(self.stereo_analyzer.analyze, audio, sr): 'stereo'
                }

                # Collect results as they complete
                for future in as_completed(futures):
                    analyzer_name = futures[future]
                    features = future.result()
                    fingerprint.update(features)

                    # Mark harmonic analysis method
                    if analyzer_name == 'harmonic':
                        fingerprint["_harmonic_analysis_method"] = ("sampled"
                                                                   if self.fingerprint_strategy == "sampling"
                                                                   else "full-track")
            except KeyboardInterrupt:
                # Wait for already-running threads to finish before re-raising so
                # they cannot write partial results to `fingerprint` after this
                # function returns. cancel_futures=True drops queued-but-unstarted
                # submissions (fixes #2514).
                executor.shutdown(wait=True, cancel_futures=True)
                raise
            else:
                executor.shutdown(wait=True)

            # Sanitize NaN/Inf values (replace with 0.0) and count replacements
            # so regressions in individual analyzers are surfaced rather than
            # silently hidden (fixes #2531).
            nan_replaced: list[str] = []
            for key, value in fingerprint.items():
                try:
                    if isinstance(value, (int, float, np.number)):
                        if np.isnan(value) or np.isinf(value):
                            logger.warning(
                                f"Fingerprint dimension '{key}' contains NaN/Inf, replacing with 0.0"
                            )
                            fingerprint[key] = 0.0
                            nan_replaced.append(key)
                except (TypeError, ValueError):
                    # Skip non-numeric values (like strings)
                    pass

            if nan_replaced:
                logger.warning(
                    f"Fingerprint sanitized {len(nan_replaced)} NaN/Inf dimension(s): "
                    f"{nan_replaced}. Check the contributing analyzers for bugs."
                )

            return fingerprint

        except Exception as e:
            logger.error(f"Audio fingerprint analysis failed: {e}")
            return self._get_default_fingerprint()

    def _analyze_frequency_cached(self, audio: np.ndarray, sr: int,
                                   fft: np.ndarray, magnitude: np.ndarray,
                                   freqs: np.ndarray) -> dict[str, float]:
        """
        Analyze frequency distribution (7-band) using pre-computed FFT.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate
            fft: Pre-computed FFT
            magnitude: Pre-computed magnitude spectrum
            freqs: Pre-computed frequency bins

        Returns:
            Dict with 7 frequency band percentages
        """
        try:
            # Define 7 frequency bands
            bands = {
                'sub_bass_pct': (20, 60),
                'bass_pct': (60, 250),
                'low_mid_pct': (250, 500),
                'mid_pct': (500, 2000),
                'upper_mid_pct': (2000, 4000),
                'presence_pct': (4000, 6000),
                'air_pct': (6000, 20000)
            }

            # Calculate energy per band
            band_energies = {}
            total_energy = 0

            for band_name, (low, high) in bands.items():
                mask = (freqs >= low) & (freqs < high)
                energy = np.sum(magnitude[mask] ** 2)
                band_energies[band_name] = energy
                total_energy += energy

            # Convert to normalized percentages (0-1 range for compatibility with adaptive gain calculations)
            # Do NOT multiply by 100 - keep as 0.0-1.0 for consistency with rest of system
            if total_energy > 0:
                for band_name in bands.keys():
                    band_energies[band_name] = band_energies[band_name] / total_energy
            else:
                for band_name in bands.keys():
                    band_energies[band_name] = 0.0

            return band_energies

        except Exception as e:
            logger.debug(f"Frequency analysis failed: {e}")
            # Return normalized defaults (0-1 range, must sum to 1.0)
            return {
                'sub_bass_pct': 0.05,
                'bass_pct': 0.15,
                'low_mid_pct': 0.15,
                'mid_pct': 0.30,
                'upper_mid_pct': 0.20,
                'presence_pct': 0.10,
                'air_pct': 0.05
            }

    def _analyze_dynamics_cached(self, audio: np.ndarray, sr: int,
                                  fft: np.ndarray, magnitude: np.ndarray,
                                  freqs: np.ndarray, rms: float) -> dict[str, float]:
        """
        Analyze dynamics (LUFS, crest factor, bass/mid ratio) using pre-computed values.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate
            fft: Pre-computed FFT
            magnitude: Pre-computed magnitude spectrum
            freqs: Pre-computed frequency bins
            rms: Pre-computed RMS

        Returns:
            Dict with 3 dynamics features
        """
        try:
            # 1. LUFS (approximate using RMS)
            lufs = 20 * np.log10(rms + 1e-10) + 0.691  # Approximate conversion

            # 2. Crest factor
            peak = np.max(np.abs(audio))
            crest_db = 20 * np.log10(peak / (rms + 1e-10))

            # 3. Bass/Mid ratio (using pre-computed FFT)
            bass_mask = (freqs >= 60) & (freqs < 250)
            mid_mask = (freqs >= 250) & (freqs < 2000)

            bass_energy = np.sum(magnitude[bass_mask] ** 2)
            mid_energy = np.sum(magnitude[mid_mask] ** 2)

            if mid_energy > 0:
                bass_mid_ratio = 10 * np.log10(bass_energy / mid_energy)
            else:
                bass_mid_ratio = 0.0

            return {
                'lufs': float(lufs),
                'crest_db': float(crest_db),
                'bass_mid_ratio': float(bass_mid_ratio)
            }

        except Exception as e:
            logger.debug(f"Dynamics analysis failed: {e}")
            return {
                'lufs': -20.0,
                'crest_db': 15.0,
                'bass_mid_ratio': 0.0
            }

    def _get_default_fingerprint(self) -> dict[str, float]:
        """
        Get default fingerprint on analysis failure.

        Returns:
            Dict with 25 default values
        """
        return {
            # Frequency (7D)
            'sub_bass_pct': 5.0,
            'bass_pct': 15.0,
            'low_mid_pct': 15.0,
            'mid_pct': 30.0,
            'upper_mid_pct': 20.0,
            'presence_pct': 10.0,
            'air_pct': 5.0,
            # Dynamics (3D)
            'lufs': -20.0,
            'crest_db': 15.0,
            'bass_mid_ratio': 0.0,
            # Temporal (4D)
            'tempo_bpm': 120.0,
            'rhythm_stability': 0.5,
            'transient_density': 0.5,
            'silence_ratio': 0.1,
            # Spectral (3D)
            'spectral_centroid': 0.5,
            'spectral_rolloff': 0.5,
            'spectral_flatness': 0.3,
            # Harmonic (3D)
            'harmonic_ratio': 0.5,
            'pitch_stability': 0.7,
            'chroma_energy': 0.5,
            # Variation (3D)
            'dynamic_range_variation': 0.5,
            'loudness_variation_std': 0.5,
            'peak_consistency': 0.5,
            # Stereo (2D)
            'stereo_width': 0.5,
            'phase_correlation': 1.0
        }
