# -*- coding: utf-8 -*-

"""
Runtime Strategy Manager for Adaptive Sampling

Orchestrates strategy selection, confidence assessment, and fallback mechanisms
during fingerprint extraction. Manages transitions between sampling and full-track
strategies based on real-time feature analysis and confidence scores.

Decision Flow:
  1. Initial strategy selection (AdaptiveStrategySelector)
  2. Execute selected strategy and extract features
  3. Assess confidence in results (ConfidenceScorer)
  4. If confidence < threshold: fallback to full-track
  5. Return final features with confidence metadata

Fallback Strategies:
  - HIGH confidence (>=0.90): Use sampled results, cache confidence
  - ACCEPTABLE confidence (0.75-0.90): Use sampled results with validation flag
  - LOW confidence (<0.75): Fallback to full-track analysis
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from auralis.analysis.fingerprint.confidence_scorer import ConfidenceScorer
from auralis.analysis.fingerprint.feature_adaptive_sampler import (
    FeatureAdaptiveSampler,
)
from auralis.analysis.fingerprint.strategy_selector import (
    AdaptiveStrategySelector,
    ProcessingMode,
    StrategyPreference,
)

logger = logging.getLogger(__name__)


class ExecutionResult(Enum):
    """Result of strategy execution"""
    SUCCESS = "success"           # Strategy executed successfully
    FALLBACK = "fallback"         # Fell back to full-track
    PARTIAL = "partial"           # Partial success with validation
    ERROR = "error"               # Execution error


class RuntimeStrategyManager:
    """
    Manages runtime strategy selection, execution, and fallback mechanisms
    for adaptive fingerprint extraction.
    """

    def __init__(self) -> None:
        """Initialize runtime strategy manager."""
        self.strategy_selector = AdaptiveStrategySelector()
        self.confidence_scorer = ConfidenceScorer()
        self.feature_sampler = FeatureAdaptiveSampler()

        # Execution statistics
        self.stats = {
            "total_attempts": 0,
            "successful_sampling": 0,
            "fallback_to_fulltrack": 0,
            "partial_success": 0,
            "errors": 0,
        }

        logger.debug("RuntimeStrategyManager initialized")

    def select_and_execute_strategy(
        self,
        audio_features: Dict[str, float],
        audio_length_s: float,
        processing_mode: Optional[ProcessingMode] = None,
        sampled_features: Optional[Dict[str, float]] = None,
        full_track_features: Optional[Dict[str, float]] = None,
    ) -> Tuple[str, Dict[str, Any], ExecutionResult]:
        """
        Select optimal strategy and execute with fallback if needed.

        Args:
            audio_features: Initial audio feature analysis
            audio_length_s: Audio duration in seconds
            processing_mode: Processing context (LIBRARY_SCAN, INTERACTIVE, etc.)
            sampled_features: Pre-computed sampled strategy features (optional)
            full_track_features: Pre-computed full-track features (optional)

        Returns:
            (strategy_used, result_dict, execution_result) where:
              - strategy_used: "full-track" or "sampling"
              - result_dict: Features and metadata
              - execution_result: ExecutionResult enum
        """
        self.stats["total_attempts"] += 1

        # Step 1: Select initial strategy
        initial_strategy = self.strategy_selector.select_strategy(
            audio_length_s, processing_mode
        )

        logger.debug(
            f"Initial strategy selected: {initial_strategy} "
            f"(audio_length={audio_length_s}s, mode={processing_mode.value if processing_mode else 'default'})"
        )

        # Step 2: Assess confidence if we have both sampled and full-track features
        if sampled_features and full_track_features:
            confidence_score, confidence_details = self.confidence_scorer.score_features(
                sampled_features, full_track_features
            )

            tier = confidence_details["overall"]["tier"]
            recommendation = confidence_details["overall"]["recommendation"]

            logger.debug(
                f"Confidence assessment: {tier} ({confidence_score:.2f}) - {recommendation}"
            )

            # Step 3: Make fallback decision
            if confidence_score < self.confidence_scorer.acceptable_confidence_threshold:
                # LOW confidence -> fallback to full-track
                logger.info(
                    f"Low confidence ({confidence_score:.2f}) - falling back to full-track"
                )
                self.stats["fallback_to_fulltrack"] += 1

                return "full-track", {
                    "features": full_track_features,
                    "strategy": "full-track",
                    "reason": "Fallback due to low confidence",
                    "original_strategy": initial_strategy,
                    "confidence_score": confidence_score,
                    "confidence_tier": tier,
                    "sampled_available": True,
                }, ExecutionResult.FALLBACK

            elif confidence_score < self.confidence_scorer.high_confidence_threshold:
                # ACCEPTABLE confidence -> use sampling with validation flag
                logger.info(
                    f"Acceptable confidence ({confidence_score:.2f}) - "
                    f"using sampling with validation"
                )
                self.stats["partial_success"] += 1

                return "sampling", {
                    "features": sampled_features,
                    "strategy": "sampling",
                    "reason": "Acceptable confidence, validation recommended",
                    "confidence_score": confidence_score,
                    "confidence_tier": tier,
                    "validation_required": True,
                }, ExecutionResult.PARTIAL

            else:
                # HIGH confidence -> use sampling
                logger.info(
                    f"High confidence ({confidence_score:.2f}) - "
                    f"using sampling with confidence"
                )
                self.stats["successful_sampling"] += 1

                return "sampling", {
                    "features": sampled_features,
                    "strategy": "sampling",
                    "reason": "High confidence in sampled results",
                    "confidence_score": confidence_score,
                    "confidence_tier": tier,
                    "validation_required": False,
                }, ExecutionResult.SUCCESS

        else:
            # No confidence data - use initial strategy selection
            logger.debug(
                "No confidence data available - using initial strategy selection"
            )

            features_to_use = (
                sampled_features if initial_strategy == "sampling" else full_track_features
            )

            if features_to_use is None:
                logger.error(f"No features available for strategy {initial_strategy}")
                self.stats["errors"] += 1

                return initial_strategy, {
                    "features": {},
                    "strategy": initial_strategy,
                    "reason": "Error: no features available",
                }, ExecutionResult.ERROR

            self.stats["successful_sampling"] += 1
            return initial_strategy, {
                "features": features_to_use,
                "strategy": initial_strategy,
                "reason": "Strategy selection without confidence assessment",
                "confidence_score": None,
                "confidence_tier": None,
            }, ExecutionResult.SUCCESS

    def get_adaptive_sampling_params(
        self, audio_features: Dict[str, float]
    ) -> Tuple[str, float]:
        """
        Get adaptive sampling parameters based on audio characteristics.

        Args:
            audio_features: Audio feature analysis

        Returns:
            (strategy, interval_s) where strategy is feature-optimized choice
        """
        strategy, interval, reasoning = self.feature_sampler.select_sampling_strategy(
            audio_features
        )

        logger.debug(f"Adaptive sampling strategy: {strategy.value}, interval={interval}s")
        logger.debug(f"Reasoning: {reasoning}")

        return strategy.value, interval

    def should_validate_results(self, confidence_score: float) -> bool:
        """
        Determine if sampled results should be validated against full-track.

        Args:
            confidence_score: Confidence score (0.0-1.0)

        Returns:
            True if validation recommended
        """
        return (
            confidence_score < self.confidence_scorer.high_confidence_threshold
            and confidence_score >= self.confidence_scorer.acceptable_confidence_threshold
        )

    def set_user_preference(self, preference: StrategyPreference) -> None:
        """
        Set user strategy preference.

        Args:
            preference: QUALITY, SPEED, BALANCED, or AUTO
        """
        self.strategy_selector.set_user_preference(preference)
        logger.info(f"User preference set to: {preference.value}")

    def set_fallback_thresholds(
        self,
        high_confidence: Optional[float] = None,
        acceptable_confidence: Optional[float] = None,
    ) -> None:
        """
        Configure fallback confidence thresholds.

        Args:
            high_confidence: Score >= this = no fallback (default 0.90)
            acceptable_confidence: Score >= this = partial success (default 0.75)
        """
        self.confidence_scorer.configure_thresholds(
            high_confidence=high_confidence,
            acceptable_confidence=acceptable_confidence,
        )

        logger.info(
            f"Fallback thresholds configured: "
            f"high={self.confidence_scorer.high_confidence_threshold}, "
            f"acceptable={self.confidence_scorer.acceptable_confidence_threshold}"
        )

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics.

        Returns:
            Dict with execution counts and rates
        """
        total = self.stats["total_attempts"]
        if total == 0:
            return self.stats.copy()

        sampling_rate = (
            self.stats["successful_sampling"] / total * 100 if total > 0 else 0
        )
        fallback_rate = (
            self.stats["fallback_to_fulltrack"] / total * 100 if total > 0 else 0
        )
        partial_rate = self.stats["partial_success"] / total * 100 if total > 0 else 0
        error_rate = self.stats["errors"] / total * 100 if total > 0 else 0

        return {
            **self.stats,
            "sampling_rate_%": sampling_rate,
            "fallback_rate_%": fallback_rate,
            "partial_rate_%": partial_rate,
            "error_rate_%": error_rate,
        }

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self.stats = {
            "total_attempts": 0,
            "successful_sampling": 0,
            "fallback_to_fulltrack": 0,
            "partial_success": 0,
            "errors": 0,
        }
        logger.info("Execution statistics reset")


def create_default_strategy_manager() -> RuntimeStrategyManager:
    """
    Factory function to create a default runtime strategy manager.

    Returns:
        RuntimeStrategyManager with default configuration
    """
    return RuntimeStrategyManager()
