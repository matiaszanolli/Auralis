"""
Content-Aware Audio Analyzer

Analyzes audio content WITHOUT making assumptions based on metadata or genre labels.
Implements the "Never Assume" principle: analyze the actual audio characteristics.

Based on 7 genre profile analysis (October 26, 2025):
- Steven Wilson 2021, 2024 (Progressive Rock - Audiophile)
- AC/DC (Classic Hard Rock - Mid-dominant)
- Blind Guardian (Power Metal - Modern)
- Bob Marley (Reggae - Groove-focused)
- Joe Satriani (Commercial Rock - Loudness War)
- Dio (Traditional Heavy Metal - 2005 Remaster)

Key Discovery: Bass/Mid Ratio is the strongest differentiator (8.9 dB range)
"""

import logging
from typing import Any, Dict, Tuple

import numpy as np

from .fingerprint.common_metrics import SafeOperations

logger = logging.getLogger(__name__)


class ContentAwareAnalyzer:
    """
    Analyzes audio content to detect musical characteristics without assumptions.

    This analyzer focuses on WHAT THE AUDIO ACTUALLY SOUNDS LIKE, not what
    genre labels or metadata claim it should be.

    Key Insights from 7 Profile Analysis:
    1. Bass/Mid Ratio: -3.4 to +5.5 dB (strongest differentiator)
    2. Crest Factor: 10.5 to 21.1 dB (mastering philosophy indicator)
    3. Bass Energy: 30.9% to 74.6% (production era indicator)
    4. Mid Energy: 21.3% to 66.9% (classic vs modern indicator)
    """

    def __init__(self) -> None:
        """Initialize content analyzer."""
        self.frequency_bands: Dict[str, Tuple[int, int]] = {
            'bass': (20, 250),      # Bass fundamentals
            'mid': (250, 4000),     # Vocals, guitars, core musical content
            'high': (4000, 20000)   # Cymbals, air, presence
        }

    def analyze(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """
        Complete content analysis of audio.

        Args:
            audio: Audio samples (mono or will be converted to mono)
            sr: Sample rate

        Returns:
            Dictionary with:
            - spectral: Frequency characteristics
            - dynamic: Dynamic range characteristics
            - energy: Intensity characteristics
            - profile_match: Closest profile match
            - confidence: Match confidence (0-1)
        """
        # Ensure mono
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)

        # Run all analyses
        spectral = self._analyze_spectral_content(audio, sr)
        dynamic = self._analyze_dynamic_content(audio)
        energy = self._analyze_energy_content(audio, sr)

        # Match to profile based on content
        profile_match, confidence = self._match_to_profile(spectral, dynamic, energy)

        return {
            'spectral': spectral,
            'dynamic': dynamic,
            'energy': energy,
            'profile_match': profile_match,
            'confidence': confidence,
            'characteristics': self._describe_characteristics(spectral, dynamic, energy)
        }

    def _analyze_spectral_content(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """
        Analyze frequency content.

        Key Insight: Bass/Mid ratio is the strongest differentiator between
        classic rock (-3.4 dB), balanced audiophile (+0.9 dB), and modern
        metal (+3.8 to +5.5 dB).
        """
        # FFT analysis
        fft = np.fft.rfft(audio)
        freqs = np.fft.rfftfreq(len(audio), 1/sr)
        magnitude = np.abs(fft)

        # Calculate energy in each band
        bass_mask = (freqs >= self.frequency_bands['bass'][0]) & \
                    (freqs < self.frequency_bands['bass'][1])
        mid_mask = (freqs >= self.frequency_bands['mid'][0]) & \
                   (freqs < self.frequency_bands['mid'][1])
        high_mask = (freqs >= self.frequency_bands['high'][0]) & \
                    (freqs <= self.frequency_bands['high'][1])

        bass_energy = np.sum(magnitude[bass_mask]**2)
        mid_energy = np.sum(magnitude[mid_mask]**2)
        high_energy = np.sum(magnitude[high_mask]**2)
        total_energy = bass_energy + mid_energy + high_energy

        # Percentages (using SafeOperations for safe division)
        bass_pct = SafeOperations.safe_divide(bass_energy, total_energy, fallback=0.0) * 100
        mid_pct = SafeOperations.safe_divide(mid_energy, total_energy, fallback=0.0) * 100
        high_pct = SafeOperations.safe_divide(high_energy, total_energy, fallback=0.0) * 100

        # Ratios in dB (key differentiators!) - use safe division with epsilon protection
        bass_to_mid_ratio = SafeOperations.safe_divide(bass_energy, mid_energy, fallback=1.0)
        bass_to_mid_db = 10 * np.log10(np.maximum(bass_to_mid_ratio, SafeOperations.EPSILON))

        high_to_mid_ratio = SafeOperations.safe_divide(high_energy, mid_energy, fallback=1.0)
        high_to_mid_db = 10 * np.log10(np.maximum(high_to_mid_ratio, SafeOperations.EPSILON))

        # Spectral characteristics
        spectral_centroid = self._calculate_spectral_centroid(magnitude, freqs)

        return {
            'bass_pct': bass_pct,
            'mid_pct': mid_pct,
            'high_pct': high_pct,
            'bass_to_mid_db': bass_to_mid_db,
            'high_to_mid_db': high_to_mid_db,
            'spectral_centroid': spectral_centroid
        }

    def _analyze_dynamic_content(self, audio: np.ndarray) -> Dict[str, Any]:
        """
        Analyze dynamic range characteristics.

        Key Insight: Crest factor indicates mastering philosophy:
        - >17 dB: Audiophile (Steven Wilson, AC/DC)
        - 14-17 dB: Balanced (Blind Guardian)
        - <12 dB: Loudness War (Dio, Joe Satriani, Bob Marley)
        """
        # RMS calculation
        rms = np.sqrt(np.mean(audio**2))
        rms_db = 20 * np.log10(rms) if rms > 0 else -100

        # Peak calculation
        peak = np.max(np.abs(audio))
        peak_db = 20 * np.log10(peak) if peak > 0 else -100

        # Crest factor (THE key dynamic indicator)
        crest_factor_db = peak_db - rms_db

        # Estimate LUFS (rough approximation)
        estimated_lufs = rms_db + 3.0

        # Dynamic variation analysis
        # Split into 1-second windows and measure RMS variation
        window_size = 44100  # 1 second at 44.1kHz
        if len(audio) > window_size:
            num_windows = len(audio) // window_size
            window_rms = []
            for i in range(num_windows):
                window = audio[i*window_size:(i+1)*window_size]
                window_rms.append(np.sqrt(np.mean(window**2)))
            rms_variation_db = 20 * np.log10(np.std(window_rms) / np.mean(window_rms)) \
                               if np.mean(window_rms) > 0 else 0
        else:
            rms_variation_db = 0

        return {
            'rms_db': rms_db,
            'peak_db': peak_db,
            'crest_factor_db': crest_factor_db,
            'estimated_lufs': estimated_lufs,
            'rms_variation_db': rms_variation_db
        }

    def _analyze_energy_content(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """
        Analyze energy and intensity characteristics.
        """
        # Overall energy
        rms = np.sqrt(np.mean(audio**2))

        # Spectral flux (measure of change/intensity)
        spectral_flux = self._calculate_spectral_flux(audio, sr)

        return {
            'rms': rms,
            'spectral_flux': spectral_flux
        }

    def _match_to_profile(self, spectral: Dict[str, Any], dynamic: Dict[str, Any], energy: Dict[str, Any]) -> Tuple[str, float]:
        """
        Match content to one of the 7 profiles based on audio characteristics.

        Decision tree based on 7 profile analysis:
        1. AC/DC is unique: Mid-dominant (>55% mid, negative B/M ratio)
        2. Steven Wilson split by crest factor and bass energy
        3. Loudness war era: <12 dB crest
        4. Use combination of features for reliable detection

        Returns:
            (profile_name, confidence)
        """
        bass_mid_ratio = spectral['bass_to_mid_db']
        crest = dynamic['crest_factor_db']
        bass_pct = spectral['bass_pct']
        mid_pct = spectral['mid_pct']
        lufs = dynamic['estimated_lufs']

        # Track confidence (how certain we are)
        confidence = 0.0
        profile = 'unknown'

        # 1. Classic Rock Detection (MOST UNIQUE SIGNATURE)
        # Mid-dominance is extremely rare - check this FIRST
        if mid_pct > 50 and bass_mid_ratio < 0:
            profile = 'acdc_highway_to_hell'
            confidence = 0.95  # Very distinctive
            logger.info(f"Detected classic rock: mid-dominant ({mid_pct:.1f}% mid, {bass_mid_ratio:.1f} dB B/M)")

        # 2. Ultra-Audiophile Detection (Steven Wilson 2024)
        elif crest > 19:
            if bass_pct > 70:
                profile = 'steven_wilson_2024'
                confidence = 0.90
                logger.info(f"Detected ultra-audiophile: extreme dynamics ({crest:.1f} dB crest) + bass-heavy ({bass_pct:.1f}%)")
            else:
                profile = 'steven_wilson_2021'
                confidence = 0.85
                logger.info(f"Detected audiophile: extreme dynamics ({crest:.1f} dB crest) + balanced")

        # 3. Audiophile with good dynamics (Steven Wilson 2021 or AC/DC)
        elif crest > 17:
            if bass_mid_ratio > 0:
                profile = 'steven_wilson_2021'
                confidence = 0.80
                logger.info(f"Detected audiophile: good dynamics ({crest:.1f} dB) + bass-forward")
            else:
                profile = 'acdc_highway_to_hell'
                confidence = 0.75
                logger.info(f"Detected classic rock: good dynamics ({crest:.1f} dB) + mid-dominant")

        # 4. Modern Metal (Blind Guardian)
        elif 15 < crest <= 17 and bass_mid_ratio > 3:
            profile = 'blind_guardian'
            confidence = 0.85
            logger.info(f"Detected modern metal: moderate dynamics ({crest:.1f} dB) + heavy bass ({bass_mid_ratio:.1f} dB B/M)")

        # 5. Reggae Detection (high bass but not extreme, moderate dynamics)
        elif 58 < bass_pct < 70 and 11 < crest < 13 and bass_mid_ratio < 4.5:
            profile = 'bob_marley_legend'
            confidence = 0.75
            logger.info(f"Detected reggae: high bass ({bass_pct:.1f}%) + groove dynamics ({crest:.1f} dB)")

        # 6. Loudness War Era
        elif crest < 12:
            if bass_mid_ratio > 3.5:
                profile = 'joe_satriani'
                confidence = 0.85
                logger.info(f"Detected loudness war rock: low dynamics ({crest:.1f} dB) + extreme bass ({bass_mid_ratio:.1f} dB)")
            elif crest < 11.8:
                profile = 'dio_holy_diver'
                confidence = 0.80
                logger.info(f"Detected maximum loudness: very low dynamics ({crest:.1f} dB)")
            else:
                profile = 'bob_marley_legend'
                confidence = 0.70
                logger.info(f"Detected moderate loudness: low dynamics ({crest:.1f} dB)")

        # 7. Balanced approach (default)
        else:
            profile = 'steven_wilson_2021'
            confidence = 0.50
            logger.info(f"Using balanced default: crest={crest:.1f} dB, B/M={bass_mid_ratio:.1f} dB")

        return profile, confidence

    def _describe_characteristics(self, spectral: Dict[str, Any], dynamic: Dict[str, Any], energy: Dict[str, Any]) -> Dict[str, str]:
        """
        Describe audio characteristics in human-readable terms.
        """
        bass_mid_ratio = spectral['bass_to_mid_db']
        crest = dynamic['crest_factor_db']
        bass_pct = spectral['bass_pct']
        mid_pct = spectral['mid_pct']

        # Frequency balance description
        if mid_pct > 55:
            freq_balance = 'mid-dominant (classic rock style)'
        elif bass_pct > 65:
            freq_balance = 'bass-heavy (modern production)'
        elif bass_pct > 50:
            freq_balance = 'bass-forward'
        else:
            freq_balance = 'balanced'

        # Dynamic range description
        if crest > 17:
            dynamic_desc = 'highly dynamic (audiophile quality)'
        elif crest > 14:
            dynamic_desc = 'good dynamics'
        elif crest > 12:
            dynamic_desc = 'moderate dynamics'
        else:
            dynamic_desc = 'heavily compressed (loudness war)'

        # Era estimation
        if crest > 17 and bass_mid_ratio < 0:
            era = 'analog/classic era (pre-1990s)'
        elif crest > 17:
            era = 'modern audiophile (2010s+)'
        elif crest < 12:
            era = 'loudness war (2000-2015)'
        else:
            era = 'balanced modern (2015+)'

        return {
            'frequency_balance': freq_balance,
            'dynamic_range': dynamic_desc,
            'era_estimation': era,
            'bass_mid_ratio_db': bass_mid_ratio,
            'crest_factor_db': crest
        }

    def _calculate_spectral_centroid(self, magnitude: np.ndarray, freqs: np.ndarray) -> float:
        """Calculate spectral centroid (brightness measure)."""
        if np.sum(magnitude) > 0:
            return np.sum(freqs * magnitude) / np.sum(magnitude)  # type: ignore[no-any-return]
        return 0.0

    def _calculate_spectral_flux(self, audio: np.ndarray, sr: int) -> float:
        """Calculate spectral flux (measure of spectral change/intensity)."""
        # Simple implementation: windowed FFT difference
        window_size = 2048
        hop_size = 512

        if len(audio) < window_size * 2:
            return 0.0

        flux_values = []
        for i in range(0, len(audio) - window_size, hop_size):
            if i + window_size * 2 > len(audio):
                break

            window1 = audio[i:i+window_size]
            window2 = audio[i+hop_size:i+hop_size+window_size]

            fft1 = np.abs(np.fft.rfft(window1))
            fft2 = np.abs(np.fft.rfft(window2))

            flux = np.sum((fft2 - fft1)**2)
            flux_values.append(flux)

        return np.mean(flux_values) if flux_values else 0.0


def analyze_audio_content(audio: np.ndarray, sr: int) -> Dict[str, Any]:
    """
    Convenience function for content-aware analysis.

    Args:
        audio: Audio samples
        sr: Sample rate

    Returns:
        Complete content analysis dictionary
    """
    analyzer = ContentAwareAnalyzer()
    return analyzer.analyze(audio, sr)
