# -*- coding: utf-8 -*-

"""
Fingerprint Validator

Validates streaming fingerprints (13D real-time) against batch equivalents (25D full).
Provides comprehensive validation metrics and similarity scoring.

Features:
- Cosine similarity calculation between fingerprints
- Per-metric accuracy tracking and normalization
- Confidence assessment based on validation scores
- Batch vs streaming dimension alignment
- Comprehensive validation reporting

Validation Strategy:
- Compare streaming (13D) to batch (25D) first 13 dimensions
- Calculate similarity score (0-1) where 1 = perfect match
- Track per-metric accuracy to identify weak dimensions
- Assess overall confidence based on similarity and data quality
"""

import logging
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of fingerprint validation."""

    def __init__(
        self,
        is_valid: bool,
        similarity_score: float,
        metric_scores: Dict[str, float],
        confidence_level: str,
        details: Optional[Dict] = None,
    ):
        """Initialize validation result.

        Args:
            is_valid: Whether fingerprint is valid (similarity >= threshold)
            similarity_score: Cosine similarity (0-1)
            metric_scores: Per-metric accuracy scores
            confidence_level: 'high', 'medium', or 'low'
            details: Additional validation details
        """
        self.is_valid = is_valid
        self.similarity_score = similarity_score
        self.metric_scores = metric_scores
        self.confidence_level = confidence_level
        self.details = details or {}

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ValidationResult("
            f"valid={self.is_valid}, "
            f"similarity={self.similarity_score:.3f}, "
            f"confidence={self.confidence_level}"
            f")"
        )


class FingerprintValidator:
    """Validate streaming fingerprints against batch equivalents.

    Compares 13D streaming fingerprints (real-time) to 25D batch fingerprints
    (full analysis) to assess accuracy and reliability.

    Metrics Compared:
    - dynamic_range_variation (0-1)
    - loudness_variation_std (0-10)
    - peak_consistency (0-1)
    - spectral_centroid (0-1)
    - spectral_rolloff (0-1)
    - spectral_flatness (0-1)
    - tempo_bpm (40-200)
    - rhythm_stability (0-1)
    - transient_density (0-1)
    - silence_ratio (0-1)
    - harmonic_ratio (0-1)
    - pitch_stability (0-1)
    - chroma_energy (0-1)
    """

    # Similarity threshold for valid fingerprints (cosine similarity)
    SIMILARITY_THRESHOLD = 0.95  # 95% similarity required

    # Per-metric valid ranges
    METRIC_RANGES = {
        # Variation metrics
        'dynamic_range_variation': (0.0, 1.0),
        'loudness_variation_std': (0.0, 10.0),
        'peak_consistency': (0.0, 1.0),
        # Spectral metrics
        'spectral_centroid': (0.0, 1.0),
        'spectral_rolloff': (0.0, 1.0),
        'spectral_flatness': (0.0, 1.0),
        # Temporal metrics
        'tempo_bpm': (40.0, 200.0),
        'rhythm_stability': (0.0, 1.0),
        'transient_density': (0.0, 1.0),
        'silence_ratio': (0.0, 1.0),
        # Harmonic metrics
        'harmonic_ratio': (0.0, 1.0),
        'pitch_stability': (0.0, 1.0),
        'chroma_energy': (0.0, 1.0),
    }

    # Expected streaming metrics (13D)
    STREAMING_METRICS = [
        'dynamic_range_variation',
        'loudness_variation_std',
        'peak_consistency',
        'spectral_centroid',
        'spectral_rolloff',
        'spectral_flatness',
        'tempo_bpm',
        'rhythm_stability',
        'transient_density',
        'silence_ratio',
        'harmonic_ratio',
        'pitch_stability',
        'chroma_energy',
    ]

    @staticmethod
    def validate_fingerprint_pair(
        streaming: Dict[str, float],
        batch: np.ndarray,
    ) -> ValidationResult:
        """Validate streaming fingerprint against batch equivalent.

        Compares 13D streaming to first 13 dimensions of 25D batch fingerprint.

        Args:
            streaming: 13D streaming fingerprint dict
            batch: 25D batch fingerprint array

        Returns:
            ValidationResult with similarity score and per-metric accuracy
        """
        # Extract batch values for streaming metrics (first 13 dimensions)
        if isinstance(batch, np.ndarray):
            batch_dict = FingerprintValidator._array_to_dict(batch)
        else:
            batch_dict = batch

        # Calculate cosine similarity
        similarity = FingerprintValidator._cosine_similarity(streaming, batch_dict)

        # Calculate per-metric accuracy
        metric_scores = FingerprintValidator._calculate_metric_accuracy(
            streaming, batch_dict
        )

        # Assess confidence level
        confidence_level = FingerprintValidator._assess_confidence(
            similarity, metric_scores
        )

        # Determine validity
        is_valid = similarity >= FingerprintValidator.SIMILARITY_THRESHOLD

        # Calculate details with safety for empty metric scores
        metric_values = list(metric_scores.values())
        details = {
            'num_metrics': len(metric_scores),
            'avg_metric_accuracy': np.mean(metric_values) if metric_values else 0.0,
            'min_metric_accuracy': min(metric_values) if metric_values else 0.0,
            'max_metric_accuracy': max(metric_values) if metric_values else 0.0,
        }

        return ValidationResult(
            is_valid=is_valid,
            similarity_score=similarity,
            metric_scores=metric_scores,
            confidence_level=confidence_level,
            details=details,
        )

    @staticmethod
    def _array_to_dict(batch: np.ndarray) -> Dict[str, float]:
        """Convert batch fingerprint array to dict using metric names.

        Args:
            batch: 25D batch fingerprint array

        Returns:
            Dictionary with metric names and values
        """
        # Take first 13 dimensions and map to streaming metric names
        batch_dict = {}
        for i, metric_name in enumerate(FingerprintValidator.STREAMING_METRICS):
            if i < len(batch):
                batch_dict[metric_name] = float(batch[i])
        return batch_dict

    @staticmethod
    def _cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Calculate cosine similarity between two fingerprint dicts.

        Args:
            vec1: First fingerprint dict
            vec2: Second fingerprint dict

        Returns:
            Cosine similarity score (0-1)
        """
        # Get common metric names
        metrics = set(vec1.keys()) & set(vec2.keys())
        if not metrics:
            return 0.0

        # Extract values for common metrics
        v1 = np.array([vec1[m] for m in metrics])
        v2 = np.array([vec2[m] for m in metrics])

        # Calculate cosine similarity
        magnitude_product = np.linalg.norm(v1) * np.linalg.norm(v2)
        if magnitude_product == 0:
            return 0.0

        similarity = np.dot(v1, v2) / magnitude_product
        # Clamp to [0, 1]
        return max(0.0, min(1.0, float(similarity)))

    @staticmethod
    def _calculate_metric_accuracy(
        streaming: Dict[str, float],
        batch: Dict[str, float],
    ) -> Dict[str, float]:
        """Calculate per-metric accuracy (0-1).

        Args:
            streaming: Streaming fingerprint dict
            batch: Batch fingerprint dict

        Returns:
            Dictionary with metric accuracy scores
        """
        metric_scores = {}

        for metric_name in FingerprintValidator.STREAMING_METRICS:
            if metric_name not in streaming or metric_name not in batch:
                continue

            streaming_val = streaming[metric_name]
            batch_val = batch[metric_name]

            # Get metric range
            metric_range = FingerprintValidator.METRIC_RANGES.get(metric_name)
            if metric_range is None:
                # Default to 0-1 range
                metric_range = (0.0, 1.0)

            # Calculate accuracy based on normalized difference
            accuracy = FingerprintValidator._calculate_single_metric_accuracy(
                streaming_val, batch_val, metric_range
            )
            metric_scores[metric_name] = accuracy

        return metric_scores

    @staticmethod
    def _calculate_single_metric_accuracy(
        streaming_val: float,
        batch_val: float,
        metric_range: Tuple[float, float],
    ) -> float:
        """Calculate accuracy for single metric.

        Uses relative error for metrics with large ranges (tempo)
        and absolute error for normalized metrics.

        Args:
            streaming_val: Streaming metric value
            batch_val: Batch metric value
            metric_range: (min, max) range for metric

        Returns:
            Accuracy score (0-1) where 1 = perfect match
        """
        min_val, max_val = metric_range
        range_size = max_val - min_val

        # For tempo_bpm, use relative error (can vary significantly)
        if range_size > 1.0:  # Large range (e.g., tempo 40-200)
            if batch_val == 0:
                return 0.0 if streaming_val != 0 else 1.0

            relative_error = abs(streaming_val - batch_val) / abs(batch_val)
            # Map relative error to accuracy: 0% error = 1.0, 10% error = 0.9, etc.
            accuracy = max(0.0, 1.0 - relative_error)
        else:
            # Normalized range (0-1): use absolute error
            abs_error = abs(streaming_val - batch_val)
            # Map to accuracy: 0 error = 1.0, range/2 error = 0.5, etc.
            accuracy = max(0.0, 1.0 - (abs_error / range_size))

        return float(np.clip(accuracy, 0.0, 1.0))

    @staticmethod
    def _assess_confidence(
        similarity_score: float,
        metric_scores: Dict[str, float],
    ) -> str:
        """Assess confidence level based on validation results.

        Args:
            similarity_score: Overall cosine similarity (0-1)
            metric_scores: Per-metric accuracy scores

        Returns:
            'high', 'medium', or 'low' confidence level
        """
        if not metric_scores:
            return 'low'

        avg_metric_accuracy = np.mean(list(metric_scores.values()))

        # High confidence: similarity >= 0.95 AND avg accuracy >= 0.90
        if similarity_score >= 0.95 and avg_metric_accuracy >= 0.90:
            return 'high'

        # Medium confidence: similarity >= 0.85 AND avg accuracy >= 0.80
        if similarity_score >= 0.85 and avg_metric_accuracy >= 0.80:
            return 'medium'

        # Low confidence otherwise
        return 'low'

    @staticmethod
    def is_valid_fingerprint(fingerprint: Dict[str, float]) -> bool:
        """Check if fingerprint has valid value ranges.

        Args:
            fingerprint: Fingerprint dict to validate

        Returns:
            True if all metrics are within valid ranges
        """
        for metric_name, value in fingerprint.items():
            if metric_name not in FingerprintValidator.METRIC_RANGES:
                continue

            min_val, max_val = FingerprintValidator.METRIC_RANGES[metric_name]
            if not (min_val <= value <= max_val):
                logger.warning(
                    f"Metric {metric_name}={value} out of range [{min_val}, {max_val}]"
                )
                return False

        return True

    @staticmethod
    def get_metric_description(metric_name: str) -> str:
        """Get human-readable description of metric.

        Args:
            metric_name: Name of metric

        Returns:
            Metric description string
        """
        descriptions = {
            'dynamic_range_variation': 'Dynamic range variation (0-1)',
            'loudness_variation_std': 'Loudness variation standard deviation (0-10 dB)',
            'peak_consistency': 'Peak consistency (0-1)',
            'spectral_centroid': 'Spectral centroid / brightness (0-1)',
            'spectral_rolloff': 'Spectral rolloff / high freq content (0-1)',
            'spectral_flatness': 'Spectral flatness / noise-like (0-1)',
            'tempo_bpm': 'Tempo in BPM (40-200)',
            'rhythm_stability': 'Rhythm stability / beat consistency (0-1)',
            'transient_density': 'Transient density / percussion (0-1)',
            'silence_ratio': 'Silence ratio (0-1)',
            'harmonic_ratio': 'Harmonic ratio / harmonic content (0-1)',
            'pitch_stability': 'Pitch stability / frequency consistency (0-1)',
            'chroma_energy': 'Chroma energy / pitch class concentration (0-1)',
        }
        return descriptions.get(metric_name, metric_name)
