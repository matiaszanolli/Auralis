# -*- coding: utf-8 -*-

"""
Feature-Level Adaptive Sampling for Fingerprint Extraction

Enables different sampling strategies based on dominant audio characteristics:
  - Harmonic-rich (melody, vocals): CQT-optimized sampling
  - Percussive-heavy (drums, rhythm): Temporal-optimized sampling
  - Mixed content: Standard 20s interval sampling
  - Speech/sparse features: Adaptive interval based on feature stability

Strategy Selection:
  - High harmonic energy (>0.7): Use CQT with tighter intervals (10-15s)
  - High percussive energy (>0.7): Use temporal with 20s standard
  - Mixed content: Use standard 20s interval
  - Low overall energy: Use extended intervals (25-30s)

Phase 7B Validation:
  - Standard 20s interval confirmed optimal (no benefit from tighter intervals)
  - No dramatic-change handling needed (genre-agnostic)
  - This module adds optional fine-tuning for specific use cases
"""

import logging
from typing import Dict, Optional, Tuple
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class SamplingStrategy(Enum):
    """Sampling strategies for different audio characteristics"""
    STANDARD = "standard"          # 20s interval, balanced approach
    CQT_OPTIMIZED = "cqt"          # 10-15s, harmonic-rich audio
    TEMPORAL_OPTIMIZED = "temporal" # 20s, percussive-heavy audio
    ADAPTIVE = "adaptive"          # Interval varies by feature stability
    EXTENDED = "extended"          # 25-30s, sparse/low-energy audio


class FeatureAdaptiveSampler:
    """
    Selects feature-optimized sampling strategies based on audio content analysis.
    """

    def __init__(self):
        """Initialize feature-adaptive sampler."""
        # Feature energy thresholds (0.0-1.0)
        self.harmonic_threshold = 0.70     # Harmonic-rich if > this
        self.percussive_threshold = 0.70   # Percussive-heavy if > this
        self.energy_threshold = 0.30       # Low energy if < this

        # Sampling intervals (seconds)
        self.standard_interval_s = 20.0
        self.cqt_interval_s = 12.0         # Tighter for harmonic detail
        self.temporal_interval_s = 20.0    # Standard for percussive
        self.extended_interval_s = 27.0    # Longer for sparse content

        logger.debug("FeatureAdaptiveSampler initialized")

    def select_sampling_strategy(
        self, audio_features: Dict[str, float]
    ) -> Tuple[SamplingStrategy, float, str]:
        """
        Select feature-optimized sampling strategy based on audio characteristics.

        Args:
            audio_features: Dict with keys like 'harmonic_energy', 'percussive_energy', 'rms_energy'

        Returns:
            (strategy, interval_s, reasoning) where:
              - strategy: SamplingStrategy enum value
              - interval_s: Recommended sampling interval in seconds
              - reasoning: String explaining selection rationale
        """
        harmonic_energy = audio_features.get("harmonic_energy", 0.5)
        percussive_energy = audio_features.get("percussive_energy", 0.5)
        rms_energy = audio_features.get("rms_energy", 0.5)

        # Determine content type
        is_harmonic_rich = harmonic_energy > self.harmonic_threshold
        is_percussive_heavy = percussive_energy > self.percussive_threshold
        is_low_energy = rms_energy < self.energy_threshold

        # Decision tree for strategy selection
        if is_low_energy:
            strategy = SamplingStrategy.EXTENDED
            interval = self.extended_interval_s
            reasoning = (
                f"Low energy content (RMS={rms_energy:.2f}) - "
                f"using extended interval for stability"
            )
        elif is_harmonic_rich and not is_percussive_heavy:
            strategy = SamplingStrategy.CQT_OPTIMIZED
            interval = self.cqt_interval_s
            reasoning = (
                f"Harmonic-rich content (harmonic={harmonic_energy:.2f}, "
                f"percussive={percussive_energy:.2f}) - "
                f"using CQT-optimized sampling for melody/vocal detail"
            )
        elif is_percussive_heavy and not is_harmonic_rich:
            strategy = SamplingStrategy.TEMPORAL_OPTIMIZED
            interval = self.temporal_interval_s
            reasoning = (
                f"Percussive-heavy content (percussive={percussive_energy:.2f}, "
                f"harmonic={harmonic_energy:.2f}) - "
                f"using temporal sampling for rhythm accuracy"
            )
        else:
            # Mixed or standard content
            strategy = SamplingStrategy.STANDARD
            interval = self.standard_interval_s
            reasoning = (
                f"Mixed content (harmonic={harmonic_energy:.2f}, "
                f"percussive={percussive_energy:.2f}) - "
                f"using standard 20s interval"
            )

        logger.debug(f"Strategy: {strategy.value}, Interval: {interval}s, Reason: {reasoning}")
        return strategy, interval, reasoning

    def should_use_adaptive_intervals(
        self, chunk_features: list, stability_threshold: float = 0.80
    ) -> Tuple[bool, Dict]:
        """
        Determine if adaptive interval sampling should be used based on
        feature stability across chunks.

        Args:
            chunk_features: List of feature dicts from consecutive chunks
            stability_threshold: Coefficient of variation threshold (lower = more stable)

        Returns:
            (should_adapt, details) where:
              - should_adapt: True if adaptive intervals recommended
              - details: Dict with stability analysis
        """
        if len(chunk_features) < 3:
            return False, {"error": "Need >= 3 chunks for stability analysis"}

        # Compute coefficient of variation for key features
        cvs = {}
        for feature_name in ["spectral_centroid", "harmonic_energy", "percussive_energy"]:
            values = [chunk.get(feature_name, 0) for chunk in chunk_features]

            if not values or all(v == 0 for v in values):
                continue

            mean_val = np.mean(values)
            if mean_val > 0:
                cv = np.std(values) / mean_val
                cvs[feature_name] = cv

        # High CV = unstable = should use adaptive intervals
        avg_cv = np.mean(list(cvs.values())) if cvs else 0.5
        should_adapt = avg_cv > stability_threshold

        details = {
            "coefficient_of_variation": avg_cv,
            "feature_cvs": cvs,
            "recommendation": (
                "Adaptive intervals" if should_adapt
                else "Fixed intervals (stable)"
            ),
        }

        logger.debug(
            f"Adaptive intervals recommendation: {details['recommendation']} "
            f"(avg_cv={avg_cv:.2f})"
        )

        return should_adapt, details

    def get_adaptive_interval(
        self,
        base_interval_s: float,
        feature_stability: float,
        audio_length_s: float,
    ) -> float:
        """
        Compute adaptive sampling interval based on feature stability.

        Args:
            base_interval_s: Base interval (e.g., 20.0 for standard)
            feature_stability: Stability score (0.0-1.0, higher = more stable)
            audio_length_s: Total audio duration

        Returns:
            Recommended interval in seconds
        """
        # High stability -> can use longer intervals
        # Low stability -> should use shorter intervals
        # Stability range maps to interval multiplier 0.8-1.2
        multiplier = 0.8 + (feature_stability * 0.4)
        adaptive_interval = base_interval_s * multiplier

        # Clamp to reasonable bounds (5s minimum, max 80% of audio)
        min_interval = 5.0
        max_interval = max(5.0, audio_length_s * 0.8)
        adaptive_interval = max(min_interval, min(max_interval, adaptive_interval))

        logger.debug(
            f"Adaptive interval: {adaptive_interval:.1f}s "
            f"(base={base_interval_s}s, stability={feature_stability:.2f})"
        )

        return adaptive_interval

    def configure_thresholds(
        self,
        harmonic_threshold: Optional[float] = None,
        percussive_threshold: Optional[float] = None,
        energy_threshold: Optional[float] = None,
    ) -> None:
        """
        Configure energy thresholds for strategy selection.

        Args:
            harmonic_threshold: Energy threshold for harmonic-rich detection
            percussive_threshold: Energy threshold for percussive-heavy detection
            energy_threshold: RMS energy threshold for low-energy detection
        """
        if harmonic_threshold is not None:
            self.harmonic_threshold = harmonic_threshold
            logger.info(f"Harmonic threshold set to {harmonic_threshold}")

        if percussive_threshold is not None:
            self.percussive_threshold = percussive_threshold
            logger.info(f"Percussive threshold set to {percussive_threshold}")

        if energy_threshold is not None:
            self.energy_threshold = energy_threshold
            logger.info(f"Energy threshold set to {energy_threshold}")

    def configure_intervals(
        self,
        standard_s: Optional[float] = None,
        cqt_s: Optional[float] = None,
        temporal_s: Optional[float] = None,
        extended_s: Optional[float] = None,
    ) -> None:
        """
        Configure sampling intervals for different strategies.

        Args:
            standard_s: Standard interval (default 20s)
            cqt_s: CQT-optimized interval (default 12s)
            temporal_s: Temporal-optimized interval (default 20s)
            extended_s: Extended interval (default 27s)
        """
        if standard_s is not None:
            self.standard_interval_s = standard_s
            logger.info(f"Standard interval set to {standard_s}s")

        if cqt_s is not None:
            self.cqt_interval_s = cqt_s
            logger.info(f"CQT interval set to {cqt_s}s")

        if temporal_s is not None:
            self.temporal_interval_s = temporal_s
            logger.info(f"Temporal interval set to {temporal_s}s")

        if extended_s is not None:
            self.extended_interval_s = extended_s
            logger.info(f"Extended interval set to {extended_s}s")


def create_default_adaptive_sampler() -> FeatureAdaptiveSampler:
    """
    Factory function to create a default feature-adaptive sampler.

    Returns:
        FeatureAdaptiveSampler with default configuration
    """
    return FeatureAdaptiveSampler()
